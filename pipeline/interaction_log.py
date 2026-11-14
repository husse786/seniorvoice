"""SQLite interaction logger — records metrics of each pipeline turn for Grafana.

Decision A8 / F1 (14.11.2026): conversation text is never stored. Only
timings, trigger type and error codes are written. The columns user_text and
response_text stay in the schema (always empty) so existing databases and the
Grafana dashboards keep working.
"""

import sqlite3
from pathlib import Path

from config import MEMORY_DB_PATH

_INTERACTIONS_INIT_SQL = """\
CREATE TABLE IF NOT EXISTS interactions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
    trigger_type    TEXT NOT NULL,
    user_text       TEXT NOT NULL DEFAULT '',
    response_text   TEXT NOT NULL DEFAULT '',
    stt_duration_ms INTEGER,
    llm_duration_ms INTEGER,
    tts_duration_ms INTEGER,
    total_duration_ms INTEGER,
    error           TEXT DEFAULT NULL
);
"""


def _get_connection() -> sqlite3.Connection:
    db_path = Path(MEMORY_DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_INTERACTIONS_INIT_SQL)
    return conn


def log_interaction(
    trigger_type: str,
    stt_duration_ms: int | None = None,
    llm_duration_ms: int | None = None,
    tts_duration_ms: int | None = None,
    total_duration_ms: int | None = None,
    error: str | None = None,
) -> None:
    """Log the metrics of a single interaction (no conversation text)."""
    conn = _get_connection()
    try:
        conn.execute(
            "INSERT INTO interactions "
            "(trigger_type, stt_duration_ms, "
            "llm_duration_ms, tts_duration_ms, total_duration_ms, error) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (trigger_type, stt_duration_ms,
             llm_duration_ms, tts_duration_ms, total_duration_ms, error),
        )
        conn.commit()
    finally:
        conn.close()
