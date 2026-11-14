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

KINDS = ("termin", "medikament", "rueckruf")
# A7: a callback that nobody answers is "nicht erreicht" (same 2 attempts)
NICHT_ERREICHT = "nicht erreicht"

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
    columns = {row[1] for row in conn.execute("PRAGMA table_info(appointments)")}
    if "created_by_id" not in columns:
        # PR 10: portal account that entered it; NULL = senior or device setup.
        # Only this account may change or delete it (B5).
        try:
            conn.execute("ALTER TABLE appointments ADD COLUMN created_by_id TEXT")
            conn.commit()
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e):   # other process was faster
                raise
    return conn


def _to_utc(due_local: datetime) -> datetime:
    if due_local.tzinfo is None:
        due_local = due_local.replace(tzinfo=LOCAL_TZ)
    return due_local.astimezone(timezone.utc)


def _pre_minutes(kind: str, pre_minutes: int | None) -> int:
    if kind == "rueckruf":
        return 0
    if pre_minutes is None:
        # Proposal: medication reminders ring at the time itself only
        return PRE_REMINDER_MINUTES if kind == "termin" else 0
    return pre_minutes


def _insert_reminders(conn: sqlite3.Connection, appt_id: int, due: datetime,
                      pre_minutes: int, now: datetime) -> None:
    stages = [("main", due)]
    if pre_minutes > 0 and due - timedelta(minutes=pre_minutes) > now:
        stages.insert(0, ("pre", due - timedelta(minutes=pre_minutes)))
    for stage, at in stages:
        conn.execute(
            "INSERT INTO reminders (appointment_id, stage, due_at, next_attempt_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (appt_id, stage, _iso(at), _iso(at), _iso(now)),
        )


def add_appointment(title: str, due_local: datetime, created_by: str,
                    kind: str = "termin", pre_minutes: int | None = None,
                    now: datetime | None = None, created_by_id: str | None = None) -> int:
    """Store an appointment and its reminders. due_local: Swiss local time."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    if not title.strip() or not created_by.strip():
        raise ValueError("title and created_by are required")
    now = now or _now_utc()
    due = _to_utc(due_local)
    pre_minutes = _pre_minutes(kind, pre_minutes)

    conn = connect()
    try:
        cur = conn.execute(
            "INSERT INTO appointments (kind, title, due_at, created_by, created_by_id, "
            "created_at, delete_after) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (kind, title.strip(), _iso(due), created_by.strip(), created_by_id, _iso(now),
             _iso(due + timedelta(days=RETENTION_DAYS))),
        )
        appt_id = cur.lastrowid
        _insert_reminders(conn, appt_id, due, pre_minutes, now)
        conn.commit()
        return appt_id
    finally:
        conn.close()


def get_appointment(appt_id: int) -> dict | None:
    conn = connect()
    try:
        row = conn.execute(
            "SELECT id, kind, title, due_at, created_by, created_by_id FROM appointments WHERE id = ?",
            (appt_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return dict(zip(("id", "kind", "title", "due_at", "created_by", "created_by_id"), row))


def update_appointment(appt_id: int, title: str | None = None,
                       due_local: datetime | None = None, pre_minutes: int | None = None,
                       now: datetime | None = None) -> bool:
    """Change text and/or time. Reminders are planned anew (status reset).

    A reminder that is ringing right now stops on the next scheduler tick,
    because its row is replaced. False if the appointment does not exist.
    """
    now = now or _now_utc()
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT kind, title, due_at FROM appointments WHERE id = ?",
                           (appt_id,)).fetchone()
        if row is None:
            conn.rollback()
            return False
        kind, old_title, old_due = row
        new_title = old_title if title is None else title.strip()
        if not new_title:
            conn.rollback()
            raise ValueError("title is required")
        due = _parse(old_due) if due_local is None else _to_utc(due_local)
        conn.execute(
            "UPDATE appointments SET title = ?, due_at = ?, delete_after = ? WHERE id = ?",
            (new_title, _iso(due), _iso(due + timedelta(days=RETENTION_DAYS)), appt_id),
        )
        conn.execute("DELETE FROM reminders WHERE appointment_id = ?", (appt_id,))
        _insert_reminders(conn, appt_id, due, _pre_minutes(kind, pre_minutes), now)
        conn.commit()
        return True
    finally:
        conn.close()


def delete_appointment(appt_id: int) -> bool:
    """Delete an appointment and its reminders for real (secure_delete, WAL truncated)."""
    conn = connect()
    try:
        deleted = conn.execute("DELETE FROM appointments WHERE id = ?", (appt_id,)).rowcount
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()
    return deleted > 0


def list_appointments() -> list[dict]:
    """All stored appointments with their reminder status (portal view, PR 10)."""
    conn = connect()
    try:
        appts = conn.execute(
            "SELECT id, kind, title, due_at, created_by, created_by_id FROM appointments "
            "ORDER BY due_at"
        ).fetchall()
        reminders = conn.execute(
            "SELECT appointment_id, stage, due_at, status, attempts FROM reminders ORDER BY due_at"
        ).fetchall()
    finally:
        conn.close()
    by_appt: dict[int, list[dict]] = {}
    for appt_id, stage, due_at, status, attempts in reminders:
        by_appt.setdefault(appt_id, []).append(
            {"stage": stage, "due_at": due_at, "status": status, "attempts": attempts})
    keys = ("id", "kind", "title", "due_at", "created_by", "created_by_id")
    return [dict(zip(keys, row), reminders=by_appt.get(row[0], [])) for row in appts]


def _reminder_exists(reminder_id: int) -> bool:
    conn = connect()
    try:
        return conn.execute("SELECT 1 FROM reminders WHERE id = ?",
                            (reminder_id,)).fetchone() is not None
    finally:
        conn.close()


def reminder_text(kind: str, stage: str, title: str, due_utc: datetime) -> str:
    """Fixed sentence read on pickup. The title is read verbatim (B2)."""
    hhmm = due_utc.astimezone(LOCAL_TZ).strftime("%H:%M")
    if kind == "medikament":
        return f"Guten Tag. Eine Erinnerung an Ihre Medikamente: {title}."
    if kind == "rueckruf":
        return "Guten Tag. Hier ist Ihr Sprachassistent. Sie wollten, dass ich Sie anrufe. Wie geht es Ihnen?"
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
    lifted. on_hook_off() returns the sentence to announce, or None; after
    playing it the core calls announced(ok). Only a played announcement
    counts as "bestaetigt" (heard); a failed one stays retryable.

    Retry timing is stored when an attempt starts, so a restart during
    ringing neither rings again at once nor exceeds MAX_ATTEMPTS.
    """

    def __init__(self, ringer, in_call: Callable[[], bool],
                 now: Callable[[], datetime] = _now_utc,
                 monotonic: Callable[[], float] = time.monotonic):
        self.ringer = ringer
        self.in_call = in_call
        self.now = now
        self.monotonic = monotonic
        self.ringing: Ringing | None = None
        self.announcing: Ringing | None = None
        self._last_purge = 0.0

    def tick(self) -> None:
        if self.ringing is not None:
            if not _reminder_exists(self.ringing.reminder_id):
                # Changed or deleted in the portal while ringing (PR 10)
                log.info("Reminder %d removed while ringing", self.ringing.reminder_id)
                self.ringing = None
                self.ringer.stop()
            elif self.monotonic() - self.ringing.started >= RING_SECONDS:
                self._no_pickup()
            return
        # Purge also during a long call (A8), but never while a row is in use
        if self.announcing is None and self.monotonic() - self._last_purge > 3600:
            self._last_purge = self.monotonic()
            purge_expired(self.now())
        if self.in_call():
            return  # A5: during a call the reminder waits until hang-up
        self._start_next_due()

    def _start_next_due(self) -> None:
        now = self.now()
        conn = connect()
        try:
            # Too old (device was off) or all attempts used up (restart during
            # ringing): close as missed instead of ringing (A6, STALE_HOURS)
            conn.execute(
                "UPDATE reminders SET updated_at = ?, status = CASE WHEN (SELECT kind FROM "
                "appointments a WHERE a.id = reminders.appointment_id) = 'rueckruf' "
                "THEN ? ELSE ? END "
                "WHERE status IN (?, ?) AND (due_at <= ? OR (attempts >= ? AND next_attempt_at <= ?))",
                (_iso(now), NICHT_ERREICHT, VERPASST, GEPLANT, KLINGELT,
                 _iso(now - timedelta(hours=STALE_HOURS)), MAX_ATTEMPTS, _iso(now)),
            )
            conn.commit()
            row = conn.execute(
                "SELECT r.id, a.kind, r.stage, a.title, a.due_at FROM reminders r "
                "JOIN appointments a ON a.id = r.appointment_id "
                "WHERE r.status IN ('geplant', 'klingelt') AND r.attempts < ? "
                "AND r.next_attempt_at <= ? ORDER BY r.next_attempt_at LIMIT 1",
                (MAX_ATTEMPTS, _iso(now)),
            ).fetchone()
            if row is None:
                return
            rid, kind, stage, title, appt_due = row
            # Next attempt (if any) is fixed now, not when ringing ends
            next_at = now + timedelta(seconds=RING_SECONDS, minutes=RETRY_MINUTES)
            conn.execute(
                "UPDATE reminders SET status = ?, attempts = attempts + 1, next_attempt_at = ?, "
                "updated_at = ? WHERE id = ?",
                (KLINGELT, _iso(next_at), _iso(now), rid),
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
        self._attempt_failed(ringing.reminder_id, retry_at=None)

    def _attempt_failed(self, reminder_id: int, retry_at: datetime | None) -> None:
        """Missed after MAX_ATTEMPTS; otherwise the stored retry stays (or retry_at)."""
        now = self.now()
        conn = connect()
        try:
            row = conn.execute(
                "SELECT attempts FROM reminders WHERE id = ?", (reminder_id,)
            ).fetchone()
            if row is None:
                return                      # removed in the portal meanwhile
            attempts = row[0]
            if attempts >= MAX_ATTEMPTS:
                kind = conn.execute(
                    "SELECT a.kind FROM reminders r JOIN appointments a ON a.id = r.appointment_id "
                    "WHERE r.id = ?", (reminder_id,),
                ).fetchone()[0]
                final = NICHT_ERREICHT if kind == "rueckruf" else VERPASST
                conn.execute(
                    "UPDATE reminders SET status = ?, updated_at = ? WHERE id = ?",
                    (final, _iso(now), reminder_id),
                )
                log.info("Reminder %d missed after %d attempts", reminder_id, attempts)
            elif retry_at is not None:
                conn.execute(
                    "UPDATE reminders SET next_attempt_at = ?, updated_at = ? WHERE id = ?",
                    (_iso(retry_at), _iso(now), reminder_id),
                )
            conn.commit()
        finally:
            conn.close()

    def on_hook_off(self) -> str | None:
        """Handset lifted. If ringing: return the sentence to say.

        The reminder counts as heard only when the core reports announced(True).
        """
        if self.ringing is None:
            return None
        ringing, self.ringing = self.ringing, None
        self.ringer.stop()
        self.announcing = ringing
        return ringing.text

    def announced(self, ok: bool) -> None:
        """Called by the core after playing the sentence from on_hook_off()."""
        ringing, self.announcing = self.announcing, None
        if ringing is None:
            return
        if not ok:
            log.warning("Reminder %d not announced, will retry", ringing.reminder_id)
            self._attempt_failed(ringing.reminder_id,
                                 retry_at=self.now() + timedelta(minutes=RETRY_MINUTES))
            return
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


# --- Buttons "Heute" and "Kalender" (B3): fixed sentences, no LLM ---

_WEEKDAYS = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")
_MONTHS = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
           "September", "Oktober", "November", "Dezember")


def _day_name(d: datetime) -> str:
    return f"{_WEEKDAYS[d.weekday()]}, der {d.day}. {_MONTHS[d.month - 1]}"


def _hhmm(d: datetime) -> str:
    return f"{d.hour}:{d.minute:02d}" if d.minute else f"{d.hour}"


def _between(start: datetime, end: datetime, kinds: tuple[str, ...]) -> list[tuple[datetime, str, str]]:
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT due_at, kind, title FROM appointments WHERE due_at >= ? AND due_at < ? "
            f"AND kind IN ({','.join('?' * len(kinds))}) ORDER BY due_at",
            (_iso(start), _iso(end), *kinds),
        ).fetchall()
    finally:
        conn.close()
    return [(_parse(d).astimezone(LOCAL_TZ), k, t) for d, k, t in rows]


def today_text(now: datetime | None = None) -> str:
    """Heute: date, today's appointments and medication (B3)."""
    local = (now or _now_utc()).astimezone(LOCAL_TZ)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    items = _between(start, start + timedelta(days=1), ("termin", "medikament"))
    parts = [f"Heute ist {_day_name(local)}."]
    termine = [f"um {_hhmm(d)} Uhr {t}" for d, k, t in items if k == "termin"]
    meds = [f"um {_hhmm(d)} Uhr: {t}" for d, k, t in items if k == "medikament"]
    parts.append("Heute haben Sie " + ", ".join(termine) + "." if termine
                 else "Heute haben Sie keine Termine.")
    if meds:
        parts.append("Ihre Medikamente: " + "; ".join(meds) + ".")
    return " ".join(parts)


def week_text(now: datetime | None = None) -> str:
    """Kalender: appointments of the next 7 days (B3), without medication."""
    local = (now or _now_utc()).astimezone(LOCAL_TZ)
    items = _between(local, local + timedelta(days=7), ("termin",))
    if not items:
        return "In den nächsten sieben Tagen haben Sie keine Termine."
    lines = []
    for d, _k, t in items:
        day = "heute" if d.date() == local.date() else (
            "morgen" if d.date() == (local + timedelta(days=1)).date() else f"am {_day_name(d)}")
        lines.append(f"{day} um {_hhmm(d)} Uhr {t}")
    return "In den nächsten sieben Tagen haben Sie: " + "; ".join(lines) + "."
