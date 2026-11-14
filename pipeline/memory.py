"""Long-term memory: short notes about the senior, kept for at most 7 days.

Decision A8 (14.11.2026):
- Notes from conversations are deleted automatically after 7 days
  (`expires_at`, real DELETE with secure_delete, see `purge_expired`).
- No health information from conversations is stored. Health-related
  information comes only from entries by Spitex/relatives (later PRs).
- "Vergiss das" / "Vergiss alles" by voice (see `forget_all`, main.py).
- No raw conversation text is stored: only short key/value notes. The
  fallback buffer for failed extractions lives in RAM only.
"""

import json
import re
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone

from config import (
    MEMORY_DB_PATH, LLM_TIMEOUT, MEMORY_EXTRACTION_ENABLED, MEMORY_RETENTION_DAYS,
)
from llm_backend import complete as llm_complete
from logging_config import get_logger, get_content_logger

log = get_logger("memory")
content_log = get_content_logger("memory")

_EXTRACTION_RETRIES = 2   # total attempts
_CHECKPOINT_RETRIES = 10

# Categories the extraction may produce. "gesundheit" and "termine" are
# deliberately missing: no health data from conversations (A8), and
# appointments are only stored after read-back and confirmation (M11, PR 4).
ALLOWED_CATEGORIES = {"persoenlich", "vorlieben", "kontakte", "sonstiges"}

# Conservative word filter: a note is dropped if its key or value contains any
# of these stems. A 1B model cannot be trusted to leave health data out on its
# own (open question F5: residual risk is documented in the PR).
HEALTH_TERMS = (
    "gesund", "krank", "medika", "tablett", "pille", "dosis", "insulin",
    "blutdruck", "blutzucker", "zucker", "diabet", "herz", "schmerz", "arzt",
    "ärzt", "aerzt", "doktor", "spital", "klinik", "notfall", "operation",
    "therap", "diagnos", "krebs", "tumor", "demenz", "alzheimer", "parkinson",
    "depress", "psych", "angst", "schlaganfall", "infarkt", "sturz", "gestürzt",
    "gestuerzt", "rollator", "pflege", "spitex", "physio", "allergi",
    "behinder", "hörgerät", "hoergeraet", "atem",
    "lunge", "niere", "leber", "magen", "darm", "blase", "inkontinen",
    "verletz", "wunde", "fieber", "grippe", "covid", "corona", "impf",
    "rezept", "apothek", "spritze", "chemo", "dialyse", "schlafmittel",
)

_DB_INIT_SQL = """\
CREATE TABLE IF NOT EXISTS memory_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category    TEXT NOT NULL,
    key         TEXT NOT NULL,
    value       TEXT NOT NULL,
    source      TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memory_items_expires ON memory_items(expires_at);
"""

FACT_EXTRACTION_PROMPT = """\
Extrahiere kurze Notizen ueber den Benutzer aus diesem Gespraech.
Nur was der BENUTZER gesagt hat. Antworte NUR mit JSON.

Format: [{"category": "persoenlich", "key": "name", "value": "Albert"}]

Kategorien: persoenlich, vorlieben, kontakte, sonstiges
NIEMALS Gesundheit, Krankheiten, Medikamente, Aerzte oder Termine notieren.
Keine Notizen? Antworte: []

Gespraech:
"""

# Fallback buffer for failed extractions: RAM only, never on disk (A8, D14).
_pending: list[tuple[float, list[dict], str]] = []
_pending_lock = threading.Lock()


def _now() -> datetime:
    """Current time (UTC). Patched in tests to simulate the clock."""
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def retention_days() -> int:
    """Retention in days, capped at 7 (decision A8 sets 7 days as maximum)."""
    return max(0, min(MEMORY_RETENTION_DAYS, 7))


def _get_connection() -> sqlite3.Connection:
    """Open the memory database (creating the table if needed)."""
    from pathlib import Path
    db_path = Path(MEMORY_DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA secure_delete=ON")
    conn.executescript(_DB_INIT_SQL)
    return conn


def _checkpoint_truncate(conn: sqlite3.Connection) -> bool:
    """Flush and truncate the WAL so deleted notes are not left in it."""
    for _ in range(_CHECKPOINT_RETRIES):
        busy, _frames, _done = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        if busy == 0:
            return True
        time.sleep(0.2)
    log.warning("WAL checkpoint did not complete after deleting notes")
    return False


def is_health_related(fact: dict) -> bool:
    """True if a note looks like health information (category or word filter)."""
    if fact.get("category", "").strip().lower() not in ALLOWED_CATEGORIES:
        return True
    text = f"{fact.get('key', '')} {fact.get('value', '')}".lower()
    return any(term in text for term in HEALTH_TERMS)


def _filter_facts(facts: list[dict]) -> list[dict]:
    """Keep only allowed, non-health notes. Logs counts, never content."""
    kept = []
    dropped = 0
    for fact in facts:
        if is_health_related(fact):
            dropped += 1
            continue
        kept.append(fact)
    if dropped:
        log.info("Dropped %d note(s) (health or not allowed category)", dropped)
    return kept


def load_facts() -> list[dict]:
    """Load all notes that have not expired. Returns {category, key, value} dicts."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT category, key, value FROM memory_items "
            "WHERE expires_at > ? ORDER BY category, key",
            (_iso(_now()),),
        ).fetchall()
        return [{"category": r[0], "key": r[1], "value": r[2]} for r in rows]
    finally:
        conn.close()


def store_facts(facts: list[dict], source: str = "") -> int:
    """Store notes with an expiry date. A new value replaces (deletes) the old one.

    Health-related notes and other categories are dropped before storing.
    Returns the number of notes stored.
    """
    facts = _filter_facts(facts)
    if not facts:
        return 0

    now = _now()
    created = _iso(now)
    expires = _iso(now + timedelta(days=retention_days()))
    conn = _get_connection()
    stored = 0
    try:
        for fact in facts:
            cat = fact.get("category", "").strip().lower()
            key = fact.get("key", "").strip()
            val = fact.get("value", "").strip()
            if not (cat and key and val):
                continue
            conn.execute(
                "DELETE FROM memory_items WHERE category = ? AND key = ?", (cat, key)
            )
            conn.execute(
                "INSERT INTO memory_items (category, key, value, source, created_at, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (cat, key, val, source, created, expires),
            )
            stored += 1
        conn.commit()
        _checkpoint_truncate(conn)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return stored


def purge_expired() -> int:
    """Delete all expired notes for real. Returns the number deleted."""
    conn = _get_connection()
    try:
        deleted = conn.execute(
            "DELETE FROM memory_items WHERE expires_at <= ?", (_iso(_now()),)
        ).rowcount
        conn.commit()
        _checkpoint_truncate(conn)
    finally:
        conn.close()
    with _pending_lock:
        cutoff = time.time() - retention_days() * 86400
        _pending[:] = [p for p in _pending if p[0] > cutoff]
    if deleted:
        log.info("Purge: deleted %d expired note(s)", deleted)
    return deleted


def forget_all() -> int:
    """Delete every note immediately ("Vergiss alles"). Returns number deleted."""
    conn = _get_connection()
    try:
        deleted = conn.execute("DELETE FROM memory_items").rowcount
        conn.commit()
        _checkpoint_truncate(conn)
    finally:
        conn.close()
    with _pending_lock:
        _pending.clear()
    log.info("Forget all: deleted %d note(s)", deleted)
    return deleted


def format_facts_for_prompt(facts: list[dict]) -> str:
    """Format notes into a text block for the system prompt (local model only)."""
    if not facts:
        return ""

    grouped: dict[str, list[str]] = {}
    for f in facts:
        grouped.setdefault(f["category"], []).append(f"{f['key']}: {f['value']}")

    lines = ["Bekannte Informationen ueber den Benutzer:"]
    for cat, items in grouped.items():
        lines.append(f"  {cat.capitalize()}:")
        for item in items:
            lines.append(f"    - {item}")
    return "\n".join(lines)


# --- Extraction via the local LLM ---


def _call_llm_for_extraction(messages: list[dict]) -> str:
    return llm_complete(messages, timeout_override=LLM_TIMEOUT * 2)


def _parse_facts_json(raw: str) -> list[dict]:
    """Parse the LLM response into a list of note dicts (robust to small-model quirks)."""
    text = raw.strip()
    content_log.debug("Raw extraction response: %s", text[:500])
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        text = match.group(0)
    text = re.sub(r",\s*\]", "]", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        log.warning("Failed to parse facts JSON (%d chars)", len(text))
        content_log.debug("Unparseable facts JSON: %s", text[:300])
        return []
    if not isinstance(parsed, list):
        return []
    return [
        item for item in parsed
        if isinstance(item, dict) and all(k in item for k in ("category", "key", "value"))
    ]


def _do_extract(history: list[dict], source: str) -> bool:
    """Core extraction with retry. Returns True on success."""
    conversation_text = "\n".join(
        f"{'Benutzer' if m['role'] == 'user' else 'Assistent'}: {m['content']}"
        for m in history
    )
    messages = [
        {"role": "system", "content": FACT_EXTRACTION_PROMPT},
        {"role": "user", "content": conversation_text},
    ]
    for attempt in range(1, _EXTRACTION_RETRIES + 1):
        try:
            facts = _parse_facts_json(_call_llm_for_extraction(messages))
            stored = store_facts(facts, source=source)
            log.info("Extraction stored %d note(s)", stored)
            return True
        except Exception as e:
            log.warning("Extraction attempt %d/%d failed: %s", attempt, _EXTRACTION_RETRIES, type(e).__name__)
            if attempt < _EXTRACTION_RETRIES:
                time.sleep(2)
    return False


def extract_and_store_facts(history: list[dict], source: str = "") -> None:
    """Extract notes from a conversation and store them (synchronous).

    On failure the conversation is kept in RAM (never on disk) and retried
    with the next extraction, for at most the retention period.
    """
    if not history or not MEMORY_EXTRACTION_ENABLED:
        return
    if not _do_extract(history, source):
        with _pending_lock:
            _pending.append((time.time(), [m.copy() for m in history], source))
        log.info("Extraction failed; kept in RAM for retry")


def extract_facts_async(history: list[dict], source: str = "") -> None:
    """Fire-and-forget extraction in a background thread."""
    if not history or not MEMORY_EXTRACTION_ENABLED:
        return
    history_copy = [msg.copy() for msg in history]
    threading.Thread(
        target=extract_and_store_facts, args=(history_copy, source), daemon=True
    ).start()


def retry_pending_extractions() -> None:
    """Retry extractions that failed earlier in this process (RAM buffer)."""
    if not MEMORY_EXTRACTION_ENABLED:
        return
    purge_expired()
    with _pending_lock:
        items = list(_pending)
        _pending.clear()
    for _ts, history, source in items:
        extract_and_store_facts(history, source)


class PurgeService:
    """Runs purge_expired() at start and then every `interval` seconds."""

    def __init__(self, interval: float = 3600.0):
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        purge_expired()
        self._thread = threading.Thread(target=self._run, name="purge", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                purge_expired()
            except Exception as e:  # never let the purge thread die silently
                log.error("Purge failed: %s", type(e).__name__)

    def stop(self) -> None:
        self._stop.set()
