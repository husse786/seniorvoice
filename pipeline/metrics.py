"""Technical metrics in their own database (metrics.db).

What is written here: per conversation turn the durations of speech
recognition, language model and speech output, the trigger and an error code;
service events such as a restart of the dialog process. Never conversation
text (decision A8, F1).

Why a separate file: FS26 kept these metrics in the same SQLite file as the
notes about the senior, and Grafana read the whole file. Here Grafana and the
health view of the portal read only metrics.db; seniorvoice.db (notes,
appointments, Help) stays out of their reach.

The health view shows only daily values (count, median, 95th percentile):
times of single conversations would reveal the senior's daily routine.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from config import METRICS_DB_PATH

# Kept for analysis by the team; older rows are deleted (proposal, like the
# access log). Daily values in the portal cover the last 7 days.
METRICS_RETENTION_DAYS = 30

# The columns user_text and response_text stay in the schema (always empty)
# so the FS26 Grafana dashboards keep working unchanged.
_SCHEMA = """\
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
CREATE TABLE IF NOT EXISTS service_events (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
    kind      TEXT NOT NULL
);
"""

# Allowed service event kinds (a fixed list: no free text reaches this file)
EVENT_KINDS = ("dialog_restart", "dialog_hang", "core_start", "input_failed")


def connect(path: str | None = None) -> sqlite3.Connection:
    db_path = Path(path or METRICS_DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_SCHEMA)
    return conn


def log_interaction(trigger_type: str, stt_duration_ms: int | None = None,
                    llm_duration_ms: int | None = None, tts_duration_ms: int | None = None,
                    total_duration_ms: int | None = None, error: str | None = None) -> None:
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO interactions (trigger_type, stt_duration_ms, llm_duration_ms, "
            "tts_duration_ms, total_duration_ms, error) VALUES (?, ?, ?, ?, ?, ?)",
            (trigger_type, stt_duration_ms, llm_duration_ms, tts_duration_ms,
             total_duration_ms, error),
        )
        conn.commit()
    finally:
        conn.close()


def log_event(kind: str) -> None:
    if kind not in EVENT_KINDS:
        raise ValueError(f"unknown service event: {kind}")
    conn = connect()
    try:
        conn.execute("INSERT INTO service_events (kind) VALUES (?)", (kind,))
        conn.commit()
    finally:
        conn.close()


def purge(now: datetime | None = None) -> int:
    cutoff = ((now or datetime.now()) - timedelta(days=METRICS_RETENTION_DAYS)).strftime(
        "%Y-%m-%dT%H:%M:%S")
    conn = connect()
    try:
        n = conn.execute("DELETE FROM interactions WHERE timestamp < ?", (cutoff,)).rowcount
        n += conn.execute("DELETE FROM service_events WHERE timestamp < ?", (cutoff,)).rowcount
        conn.commit()
    finally:
        conn.close()
    return n


def _percentile(values: list[int], p: float) -> int | None:
    """Nearest-rank percentile (p in 0..100); None for no values."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, -(-len(ordered) * p // 100))     # ceil without math
    return ordered[int(rank) - 1]


def daily_summary(days: int = 7, now: datetime | None = None) -> list[dict]:
    """One entry per day (local date), newest first, for the last `days` days.

    Only aggregates: number of turns, errors per code, median and 95th
    percentile of the durations. "answer_ms" = speech recognition + language
    model, i.e. from the end of the question until the answer is ready (the
    target in SOLL architecture 4.4 is <= 3 s to the first spoken word).
    """
    now = now or datetime.now()
    first = (now - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT substr(timestamp, 1, 10), stt_duration_ms, llm_duration_ms, "
            "tts_duration_ms, error FROM interactions WHERE substr(timestamp, 1, 10) >= ?",
            (first,)).fetchall()
        events = conn.execute(
            "SELECT substr(timestamp, 1, 10), kind, COUNT(*) FROM service_events "
            "WHERE substr(timestamp, 1, 10) >= ? GROUP BY 1, 2", (first,)).fetchall()
    finally:
        conn.close()
    by_day: dict[str, dict] = {}
    for i in range(days):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        by_day[day] = {"date": day, "turns": 0, "errors": {}, "events": {},
                       "_stt": [], "_llm": [], "_tts": [], "_answer": []}
    for day, stt, llm, tts, error in rows:
        d = by_day.get(day)
        if d is None:
            continue
        d["turns"] += 1
        if error:
            d["errors"][error] = d["errors"].get(error, 0) + 1
            continue
        if stt is not None:
            d["_stt"].append(stt)
        if llm is not None:
            d["_llm"].append(llm)
        if tts:
            d["_tts"].append(tts)
        if stt is not None and llm is not None:
            d["_answer"].append(stt + llm)
    for day, kind, count in events:
        if day in by_day:
            by_day[day]["events"][kind] = count
    result = []
    for day in sorted(by_day, reverse=True):
        d = by_day[day]
        for key in ("stt", "llm", "tts", "answer"):
            values = d.pop(f"_{key}")
            d[f"{key}_ms"] = {"p50": _percentile(values, 50), "p95": _percentile(values, 95)}
        result.append(d)
    return result
