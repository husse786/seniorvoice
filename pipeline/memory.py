"""Persistent long-term memory — SQLite-backed fact store for SeniorVoice."""

import json
import re
import sqlite3
import threading
import time
from pathlib import Path

from config import MEMORY_DB_PATH, LLM_TIMEOUT, LLM_BACKENDS, LLM_API_KEY
from llm_backend import complete as llm_complete
from logging_config import get_logger

log = get_logger("memory")

_EXTRACTION_RETRIES = 2   # total attempts
_PENDING_DIR = Path(MEMORY_DB_PATH).parent / "pending_extractions"

_DB_INIT_SQL = """\
CREATE TABLE IF NOT EXISTS user_facts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category    TEXT NOT NULL,
    key         TEXT NOT NULL,
    value       TEXT NOT NULL,
    source      TEXT DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
    active      INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_user_facts_active ON user_facts(active) WHERE active = 1;
"""

FACT_EXTRACTION_PROMPT = """\
Extrahiere Fakten ueber den Benutzer aus diesem Gespraech.
Nur was der BENUTZER gesagt hat. Antworte NUR mit JSON.

Format: [{"category": "persoenlich", "key": "name", "value": "Albert"}]

Kategorien: persoenlich, gesundheit, vorlieben, termine, kontakte, sonstiges
Keine Fakten? Antworte: []

Gespraech:
"""


def _get_connection() -> sqlite3.Connection:
    """Open a connection to the memory database, creating it if needed."""
    db_path = Path(MEMORY_DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_DB_INIT_SQL)
    return conn


def load_facts() -> list[dict]:
    """Load all active facts. Returns list of {category, key, value} dicts."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT category, key, value FROM user_facts WHERE active = 1 ORDER BY category, key"
        ).fetchall()
        return [{"category": r[0], "key": r[1], "value": r[2]} for r in rows]
    finally:
        conn.close()


def store_facts(facts: list[dict], source: str = "") -> int:
    """Store extracted facts. Upserts: deactivates old value, inserts new.

    Each fact dict must have: category, key, value.
    Returns number of facts stored.
    """
    if not facts:
        return 0

    conn = _get_connection()
    stored = 0
    try:
        for fact in facts:
            cat = fact.get("category", "").strip()
            key = fact.get("key", "").strip()
            val = fact.get("value", "").strip()
            if not (cat and key and val):
                continue

            # Mark existing active fact as superseded
            conn.execute(
                "UPDATE user_facts SET active = 0, "
                "updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime') "
                "WHERE category = ? AND key = ? AND active = 1",
                (cat, key),
            )
            # Insert new active fact
            conn.execute(
                "INSERT INTO user_facts (category, key, value, source, active) "
                "VALUES (?, ?, ?, ?, 1)",
                (cat, key, val, source),
            )
            stored += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return stored


def format_facts_for_prompt(facts: list[dict]) -> str:
    """Format facts into a text block for the system prompt.

    Groups by category. Returns empty string if no facts.
    """
    if not facts:
        return ""

    grouped: dict[str, list[str]] = {}
    for f in facts:
        cat = f["category"]
        grouped.setdefault(cat, []).append(f"{f['key']}: {f['value']}")

    lines = ["Bekannte Informationen ueber den Benutzer:"]
    for cat, items in grouped.items():
        lines.append(f"  {cat.capitalize()}:")
        for item in items:
            lines.append(f"    - {item}")

    return "\n".join(lines)


# --- Fact extraction via LLM ---


def _call_llm_for_extraction(messages: list[dict]) -> str:
    """Raw LLM call for fact extraction via shared backend (with fallback)."""
    return llm_complete(messages, timeout_override=LLM_TIMEOUT * 2)


def _parse_facts_json(raw: str) -> list[dict]:
    """Parse the LLM response into a list of fact dicts.

    Robust against common small-model quirks: extra prose around JSON,
    markdown fences, trailing commas, single quotes.
    """
    text = raw.strip()
    log.debug("Raw extraction response: %s", text[:500])

    # Strip markdown code fences if present
    text = re.sub(r"```(?:json)?\s*", "", text).strip()

    # Try to find a JSON array anywhere in the response
    # (small models often wrap the array in explanatory text)
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        text = match.group(0)

    # Fix trailing commas before ] (common small-model mistake)
    text = re.sub(r",\s*\]", "]", text)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        log.warning("Failed to parse facts JSON: %s", text[:300])
        return []

    if not isinstance(parsed, list):
        return []

    valid = []
    for item in parsed:
        if isinstance(item, dict) and all(k in item for k in ("category", "key", "value")):
            valid.append(item)
    return valid


def _save_pending(history: list[dict], source: str) -> None:
    """Save conversation history to disk for retry on next startup."""
    _PENDING_DIR.mkdir(parents=True, exist_ok=True)
    path = _PENDING_DIR / f"{source}.json"
    path.write_text(json.dumps(history, ensure_ascii=False), encoding="utf-8")
    log.info("Saved pending extraction to %s", path)


def _process_pending() -> None:
    """Retry any pending extractions from previous failed shutdowns."""
    if not _PENDING_DIR.exists():
        return
    for path in sorted(_PENDING_DIR.glob("*.json")):
        try:
            history = json.loads(path.read_text(encoding="utf-8"))
            source = path.stem
            log.info("Retrying pending extraction: %s", source)
            _do_extract(history, source)
            path.unlink()  # success — remove pending file
        except Exception as e:
            log.error("Pending retry failed (%s): %s", path.name, e)


def _do_extract(history: list[dict], source: str) -> bool:
    """Core extraction logic with retry. Returns True on success."""
    conversation_lines = []
    for msg in history:
        role = "Benutzer" if msg["role"] == "user" else "Assistent"
        conversation_lines.append(f"{role}: {msg['content']}")
    conversation_text = "\n".join(conversation_lines)

    messages = [
        {"role": "system", "content": FACT_EXTRACTION_PROMPT},
        {"role": "user", "content": conversation_text},
    ]

    for attempt in range(1, _EXTRACTION_RETRIES + 1):
        try:
            raw_response = _call_llm_for_extraction(messages)
            facts = _parse_facts_json(raw_response)
            if facts:
                stored = store_facts(facts, source=source)
                log.info("Extracted and stored %d fact(s)", stored)
            else:
                log.debug("No new facts extracted from conversation")
            return True
        except Exception as e:
            log.warning("Extraction attempt %d/%d failed: %s", attempt, _EXTRACTION_RETRIES, e)
            if attempt < _EXTRACTION_RETRIES:
                time.sleep(2)

    return False


def extract_and_store_facts(history: list[dict], source: str = "") -> None:
    """Extract facts from conversation history and store them (synchronous).

    On failure after retries, saves history to disk for retry on next startup.
    """
    if not history:
        return
    # Skip if no backend can handle extraction:
    # - "default" mode needs an API key (cloud-only)
    # - named backends (e.g. "ollama,kimi") have their own config
    if LLM_BACKENDS == "default" and not LLM_API_KEY:
        return

    success = _do_extract(history, source)
    if not success:
        _save_pending(history, source)


def extract_facts_async(history: list[dict], source: str = "") -> None:
    """Fire-and-forget fact extraction in a background thread."""
    if not history:
        return

    history_copy = [msg.copy() for msg in history]
    thread = threading.Thread(
        target=extract_and_store_facts,
        args=(history_copy, source),
        daemon=True,
    )
    thread.start()
    log.debug("Fact extraction started in background")


def retry_pending_extractions() -> None:
    """Called on startup to process any pending extractions from previous runs."""
    _process_pending()
