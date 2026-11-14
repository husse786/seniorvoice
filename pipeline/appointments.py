"""Appointments, medication reminders and the reminder scheduler.

Decisions of 14.11.2026:
- A5: the device rings like a telephone at the due time; the reminder is
  announced when the senior lifts the handset. Pre-reminder 30 minutes before
  (adjustable). If a call is running, the reminder waits until hang-up.
  "On time" = at most 1 minute after the due time.
- A6: no pickup after 2 attempts, 10 minutes apart = "verpasst". No
  automatic escalation. "bestaetigt" only means "heard", not "taken".
- B2: medication reminder texts are read out verbatim as entered by
  Spitex/relatives. No LLM in this path.
- B5: every appointment stores who entered it.
- A8: appointments are deleted 7 days after the appointment.

Runs in the core process (no LLM), so it works when the LLM hangs (A12).
"""

import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

from config import MEMORY_DB_PATH
from logging_config import get_logger

log = get_logger("appointments")

LOCAL_TZ = ZoneInfo("Europe/Zurich")
PRE_REMINDER_MINUTES = 30
RING_SECONDS = 60          # how long one attempt rings
RETRY_MINUTES = 10         # A6: second attempt after 10 minutes
MAX_ATTEMPTS = 2           # A6: then "verpasst"
RETENTION_DAYS = 7         # A8: appointment + 7 days
# Proposal: a reminder more than 2 hours overdue (device was off) is not rung
# any more but marked "verpasst", so the senior is not called hours late.
STALE_HOURS = 2

KINDS = ("termin", "medikament")

# Reminder status values (shown in the portal later, PR 10)
GEPLANT, KLINGELT, BESTAETIGT, VERPASST = "geplant", "klingelt", "bestaetigt", "verpasst"

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS appointments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT NOT NULL,
    title       TEXT NOT NULL,
    due_at      TEXT NOT NULL,
    created_by  TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    delete_after TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reminders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    appointment_id  INTEGER NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
    stage           TEXT NOT NULL,
    due_at          TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'geplant',
    attempts        INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reminders_next ON reminders(status, next_attempt_at);
"""


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def connect() -> sqlite3.Connection:
    path = Path(MEMORY_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA secure_delete=ON")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA)
    return conn


def add_appointment(title: str, due_local: datetime, created_by: str,
                    kind: str = "termin", pre_minutes: int | None = None,
                    now: datetime | None = None) -> int:
    """Store an appointment and its reminders. due_local: Swiss local time."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    if not title.strip() or not created_by.strip():
        raise ValueError("title and created_by are required")
    now = now or _now_utc()
    if due_local.tzinfo is None:
        due_local = due_local.replace(tzinfo=LOCAL_TZ)
    due = due_local.astimezone(timezone.utc)
    if pre_minutes is None:
        # Proposal: medication reminders ring at the time itself only
        pre_minutes = PRE_REMINDER_MINUTES if kind == "termin" else 0

    conn = connect()
    try:
        cur = conn.execute(
            "INSERT INTO appointments (kind, title, due_at, created_by, created_at, delete_after) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (kind, title.strip(), _iso(due), created_by.strip(), _iso(now),
             _iso(due + timedelta(days=RETENTION_DAYS))),
        )
        appt_id = cur.lastrowid
        stages = [("main", due)]
        if pre_minutes > 0 and due - timedelta(minutes=pre_minutes) > now:
            stages.insert(0, ("pre", due - timedelta(minutes=pre_minutes)))
        for stage, at in stages:
            conn.execute(
                "INSERT INTO reminders (appointment_id, stage, due_at, next_attempt_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (appt_id, stage, _iso(at), _iso(at), _iso(now)),
            )
        conn.commit()
        return appt_id
    finally:
        conn.close()


def reminder_text(kind: str, stage: str, title: str, due_utc: datetime) -> str:
    """Fixed sentence read on pickup. The title is read verbatim (B2)."""
    hhmm = due_utc.astimezone(LOCAL_TZ).strftime("%H:%M")
    if kind == "medikament":
        return f"Guten Tag. Eine Erinnerung an Ihre Medikamente: {title}."
    if stage == "pre":
        return f"Guten Tag. Eine Erinnerung: Um {hhmm} Uhr haben Sie {title}."
    return f"Guten Tag. Eine Erinnerung: Jetzt, um {hhmm} Uhr, haben Sie {title}."


def list_reminders(conn: sqlite3.Connection | None = None) -> list[dict]:
    own = conn is None
    conn = conn or connect()
    try:
        rows = conn.execute(
            "SELECT r.id, a.kind, a.title, r.stage, r.due_at, r.status, r.attempts, a.created_by "
            "FROM reminders r JOIN appointments a ON a.id = r.appointment_id ORDER BY r.due_at"
        ).fetchall()
    finally:
        if own:
            conn.close()
    keys = ("id", "kind", "title", "stage", "due_at", "status", "attempts", "created_by")
    return [dict(zip(keys, r)) for r in rows]


@dataclass
class Ringing:
    reminder_id: int
    text: str
    started: float          # monotonic


class ReminderScheduler:
    """Ticker for the core: rings, announces on pickup, marks 'verpasst'.

    The core calls tick() every second and on_hook_off() when the handset is
    lifted. on_hook_off() returns the sentence to announce, or None.
    """

    def __init__(self, ringer, in_call: Callable[[], bool],
                 now: Callable[[], datetime] = _now_utc,
                 monotonic: Callable[[], float] = time.monotonic):
        self.ringer = ringer
        self.in_call = in_call
        self.now = now
        self.monotonic = monotonic
        self.ringing: Ringing | None = None
        self._last_purge = 0.0

    def tick(self) -> None:
        if self.ringing is not None:
            if self.monotonic() - self.ringing.started >= RING_SECONDS:
                self._no_pickup()
            return
        if self.in_call():
            return  # A5: during a call the reminder waits until hang-up
        self._start_next_due()
        if self.monotonic() - self._last_purge > 3600:
            self._last_purge = self.monotonic()
            purge_expired(self.now())

    def _start_next_due(self) -> None:
        now = self.now()
        conn = connect()
        try:
            conn.execute(
                "UPDATE reminders SET status = ?, updated_at = ? "
                "WHERE status = ? AND due_at <= ?",
                (VERPASST, _iso(now), GEPLANT, _iso(now - timedelta(hours=STALE_HOURS))),
            )
            conn.commit()
            row = conn.execute(
                "SELECT r.id, a.kind, r.stage, a.title, a.due_at FROM reminders r "
                "JOIN appointments a ON a.id = r.appointment_id "
                "WHERE r.status IN ('geplant', 'klingelt') AND r.next_attempt_at <= ? "
                "ORDER BY r.next_attempt_at LIMIT 1",
                (_iso(now),),
            ).fetchone()
            if row is None:
                return
            rid, kind, stage, title, appt_due = row
            conn.execute(
                "UPDATE reminders SET status = ?, attempts = attempts + 1, updated_at = ? WHERE id = ?",
                (KLINGELT, _iso(now), rid),
            )
            conn.commit()
        finally:
            conn.close()
        self.ringing = Ringing(rid, reminder_text(kind, stage, title, _parse(appt_due)), self.monotonic())
        self.ringer.ring()
        log.info("Reminder %d ringing", rid)

    def _no_pickup(self) -> None:
        ringing, self.ringing = self.ringing, None
        self.ringer.stop()
        now = self.now()
        conn = connect()
        try:
            attempts = conn.execute(
                "SELECT attempts FROM reminders WHERE id = ?", (ringing.reminder_id,)
            ).fetchone()[0]
            if attempts >= MAX_ATTEMPTS:
                conn.execute(
                    "UPDATE reminders SET status = ?, updated_at = ? WHERE id = ?",
                    (VERPASST, _iso(now), ringing.reminder_id),
                )
                log.info("Reminder %d missed after %d attempts", ringing.reminder_id, attempts)
            else:
                conn.execute(
                    "UPDATE reminders SET next_attempt_at = ?, updated_at = ? WHERE id = ?",
                    (_iso(now + timedelta(minutes=RETRY_MINUTES)), _iso(now), ringing.reminder_id),
                )
            conn.commit()
        finally:
            conn.close()

    def on_hook_off(self) -> str | None:
        """Handset lifted. If ringing: mark heard, return the sentence to say."""
        if self.ringing is None:
            return None
        ringing, self.ringing = self.ringing, None
        self.ringer.stop()
        conn = connect()
        try:
            conn.execute(
                "UPDATE reminders SET status = ?, updated_at = ? WHERE id = ?",
                (BESTAETIGT, _iso(self.now()), ringing.reminder_id),
            )
            conn.commit()
        finally:
            conn.close()
        log.info("Reminder %d heard", ringing.reminder_id)
        return ringing.text


def purge_expired(now: datetime | None = None) -> int:
    """Delete appointments (and their reminders) 7 days after the appointment."""
    now = now or _now_utc()
    conn = connect()
    try:
        deleted = conn.execute(
            "DELETE FROM appointments WHERE delete_after <= ?", (_iso(now),)
        ).rowcount
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()
    if deleted:
        log.info("Purge: deleted %d expired appointment(s)", deleted)
    return deleted
