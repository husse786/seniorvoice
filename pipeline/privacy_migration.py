"""One-time removal of conversation data stored by the FS26 version.

Decisions of 14.11.2026:
- A8 / F1: conversation text is never stored, not in the database and not in
  log files.
- F2: conversation data that the FS26 version already stored on the device is
  deleted the first time this version starts.

What the FS26 version left behind, and what this module removes:
- table `interactions`: full user and assistant text of every turn
  (columns are emptied; timings stay for Grafana)
- table `user_facts`: extracted facts incl. health, never deleted
  (all rows deleted; PR 2 replaces it with `memory_items`, 7 days)
- `pending_extractions/`: whole conversations as JSON files
- log files: "User said: ..." / "Response: ..." in plain text
- `response.wav`: last spoken answer in OUTPUT_DIR

The purge runs once and records itself in table `privacy_meta`. It is
idempotent: later starts only clean up leftover audio files.
"""

import shutil
import sqlite3
import time
from pathlib import Path

from config import MEMORY_DB_PATH, LOG_DIR, OUTPUT_DIR
from logging_config import get_logger

log = get_logger("privacy")

PURGE_MARKER = "legacy_purge_v1"
# v2 (PR 2): the FS26 table user_facts is replaced by memory_items
DROP_USER_FACTS_MARKER = "drop_user_facts_v2"
_LEGACY_OUTPUT_DIR = Path("/tmp/seniorvoice")
_CHECKPOINT_RETRIES = 10


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _connect() -> sqlite3.Connection:
    db_path = Path(MEMORY_DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    # Overwrite deleted content with zeros instead of only unlinking pages
    conn.execute("PRAGMA secure_delete=ON")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS privacy_meta ("
        " key TEXT PRIMARY KEY,"
        " done_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime'))"
        ")"
    )
    return conn


def checkpoint_truncate(conn: sqlite3.Connection, retries: int = _CHECKPOINT_RETRIES) -> bool:
    """Run wal_checkpoint(TRUNCATE) until it completes. Returns True on success.

    A plain checkpoint is not enough: old pages can stay readable in the WAL
    file. TRUNCATE only succeeds fully when no reader blocks it (busy == 0).
    """
    for attempt in range(1, retries + 1):
        busy, _log_frames, _checkpointed = conn.execute(
            "PRAGMA wal_checkpoint(TRUNCATE)"
        ).fetchone()
        if busy == 0:
            return True
        log.warning("WAL checkpoint blocked (attempt %d/%d), retrying", attempt, retries)
        time.sleep(0.5)
    return False


def _purge_database() -> bool:
    """Remove legacy conversation data from SQLite. Returns True when done."""
    conn = _connect()
    try:
        if conn.execute(
            "SELECT 1 FROM privacy_meta WHERE key = ?", (PURGE_MARKER,)
        ).fetchone():
            return True

        emptied = deleted = 0
        if _table_exists(conn, "interactions"):
            emptied = conn.execute(
                "UPDATE interactions SET user_text = '', response_text = '' "
                "WHERE user_text != '' OR response_text != ''"
            ).rowcount
        if _table_exists(conn, "user_facts"):
            deleted = conn.execute("DELETE FROM user_facts").rowcount
        conn.commit()

        # Rewrite the file so no freed page keeps old text, then clear the WAL.
        conn.execute("VACUUM")
        if not checkpoint_truncate(conn):
            log.error("Legacy purge: WAL checkpoint did not complete; will retry on next start")
            return False

        conn.execute("INSERT INTO privacy_meta (key) VALUES (?)", (PURGE_MARKER,))
        conn.commit()
        checkpoint_truncate(conn)
        log.info(
            "Legacy purge: emptied text of %d interaction(s), deleted %d fact(s)",
            emptied, deleted,
        )
        return True
    finally:
        conn.close()


def _purge_files() -> None:
    """Remove legacy files that contain conversation content."""
    pending_dir = Path(MEMORY_DB_PATH).parent / "pending_extractions"
    if pending_dir.exists():
        count = len(list(pending_dir.glob("*.json")))
        shutil.rmtree(pending_dir)  # errors propagate: purge must not be marked done
        log.info("Legacy purge: removed %d pending extraction file(s)", count)

    # Old log files contain "User said" / "Response" in plain text.
    removed = 0
    for path in LOG_DIR.glob("pipeline.log.*"):
        path.unlink(missing_ok=True)
        removed += 1
    current = LOG_DIR / "pipeline.log"
    if current.exists():
        # The handler has the file open in append mode; truncating is safe.
        with open(current, "r+b") as fh:
            fh.truncate(0)
        removed += 1
    if removed:
        log.info("Legacy purge: cleared %d log file(s)", removed)

    legacy_wav = _LEGACY_OUTPUT_DIR / "response.wav"
    legacy_wav.unlink(missing_ok=True)


def cleanup_audio_leftovers() -> None:
    """Delete spoken-answer files left over from a crash (runs on every start)."""
    if OUTPUT_DIR.exists():
        for path in OUTPUT_DIR.glob("response*.wav"):
            path.unlink(missing_ok=True)


def _drop_user_facts() -> None:
    """Remove the FS26 table user_facts (replaced by memory_items, 7 days)."""
    conn = _connect()
    try:
        if conn.execute(
            "SELECT 1 FROM privacy_meta WHERE key = ?", (DROP_USER_FACTS_MARKER,)
        ).fetchone():
            return
        if _table_exists(conn, "user_facts"):
            conn.execute("DELETE FROM user_facts")
            conn.execute("DROP TABLE user_facts")
            conn.commit()
            conn.execute("VACUUM")
        if not checkpoint_truncate(conn):
            raise RuntimeError("Dropping user_facts incomplete (WAL checkpoint blocked)")
        conn.execute("INSERT INTO privacy_meta (key) VALUES (?)", (DROP_USER_FACTS_MARKER,))
        conn.commit()
        checkpoint_truncate(conn)
        log.info("Removed FS26 table user_facts")
    finally:
        conn.close()


def run_legacy_purge() -> None:
    """Run the one-time legacy purge (if not done yet) and clean up audio."""
    cleanup_audio_leftovers()
    conn = _connect()
    try:
        already_done = conn.execute(
            "SELECT 1 FROM privacy_meta WHERE key = ?", (PURGE_MARKER,)
        ).fetchone() is not None
    finally:
        conn.close()
    if already_done:
        _drop_user_facts()
        return

    # Any failure stops the start: the device must not run while legacy
    # conversation data may still be on it. The purge is retried next start.
    _purge_files()  # clears old log files first, so the lines below survive
    log.info("Legacy purge: removing conversation data stored by the FS26 version")
    if not _purge_database():
        raise RuntimeError(
            "Legacy purge incomplete (WAL checkpoint blocked); refusing to start"
        )
    _drop_user_facts()
