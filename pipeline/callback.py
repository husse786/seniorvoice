"""Callback on request ("Soll ich Sie wieder anrufen?"), decision A7.

- The assistant offers a callback at most once per day, at the end of an
  everyday conversation (when the senior says goodbye).
- Only a clear "yes" counts. Anything unclear counts as no.
- The callback rings like a reminder: one retry after 10 minutes, then
  "nicht erreicht" (appointments.py). No alarm.
- The senior can cancel by voice ("Rufen Sie mich nicht an").

Callback time: the same time on the next day (confirmed 14.11.2026). Only the fact "yes, at time X" is stored, not what was
said (F1).
"""

import re
import sqlite3
from datetime import datetime, timedelta, timezone

import appointments
from appointments import LOCAL_TZ, connect

OFFER_QUESTION = (
    "Darf ich Sie morgen um {hhmm} Uhr wieder anrufen? Bitte sagen Sie Ja oder Nein."
)
CONFIRM_YES = "Gerne. Ich rufe Sie morgen um {hhmm} Uhr an. Auf Wiederhören."
CONFIRM_NO = "In Ordnung, ich rufe Sie nicht an. Auf Wiederhören."
CANCELLED = "In Ordnung. Ich habe den Anruf abgesagt."

GOODBYE = (
    "tschüss", "tschüs", "auf wiedersehen", "auf wiederhören", "adieu", "ade",
    "bis bald", "bis morgen", "schönen tag", "gute nacht", "das wars", "das war's",
    "ich lege auf", "ich muss gehen",
)
_YES = {"ja", "jawohl", "gerne", "gern", "sehr gerne", "ja gerne", "ja bitte",
        "ja gern", "ja klar", "klar", "natürlich", "ja natürlich", "ja sehr gerne"}
_NEGATION = re.compile(r"\b(nein|nicht|nö|kein|keine|lieber nicht|ungern|weiss nicht|weiß nicht|vielleicht)\b")
_CANCEL = re.compile(r"\b(nicht (mehr )?an(rufen)?|anruf absagen|rückruf absagen|rufen sie mich nicht)\b")

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS callback_offers (
    asked_on TEXT PRIMARY KEY,
    accepted INTEGER NOT NULL
);
"""


def _today_local(now: datetime) -> str:
    return now.astimezone(LOCAL_TZ).strftime("%Y-%m-%d")


def _conn() -> sqlite3.Connection:
    conn = connect()
    conn.executescript(_SCHEMA)
    return conn


def is_goodbye(text: str) -> bool:
    lower = text.lower()
    return any(re.search(rf"\b{re.escape(g)}\b", lower) for g in GOODBYE)


def is_clear_yes(answer: str) -> bool:
    """Only a short, unambiguous yes counts (A7: unclear = no)."""
    lower = answer.lower().strip()
    if _NEGATION.search(lower):
        return False
    words = re.sub(r"[^\wäöüß ]", " ", lower).split()
    if not words or len(words) > 4:
        return False
    return " ".join(words) in _YES


def is_cancel_request(text: str) -> bool:
    return bool(_CANCEL.search(text.lower()))


def may_offer(now: datetime) -> bool:
    """At most once per day (A7)."""
    conn = _conn()
    try:
        row = conn.execute(
            "SELECT 1 FROM callback_offers WHERE asked_on = ?", (_today_local(now),)
        ).fetchone()
        return row is None
    finally:
        conn.close()


def callback_time(now: datetime) -> datetime:
    """Same time tomorrow, rounded to the next 5 minutes (confirmed)."""
    local = now.astimezone(LOCAL_TZ) + timedelta(days=1)
    minute = (local.minute // 5 + 1) * 5
    local = local.replace(second=0, microsecond=0) + timedelta(minutes=minute - local.minute)
    return local


def reserve_offer(now: datetime | None = None) -> None:
    """Count today's offer before asking, so a failed recording cannot repeat it."""
    now = now or datetime.now(timezone.utc)
    conn = _conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO callback_offers (asked_on, accepted) VALUES (?, 0)",
            (_today_local(now),),
        )
        conn.commit()
    finally:
        conn.close()


def record_answer(answer: str, now: datetime | None = None) -> tuple[bool, str]:
    """Store the offer for today; schedule the callback on a clear yes.

    Returns (accepted, sentence to say).
    """
    now = now or datetime.now(timezone.utc)
    accepted = is_clear_yes(answer)
    conn = _conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO callback_offers (asked_on, accepted) VALUES (?, ?)",
            (_today_local(now), int(accepted)),
        )
        conn.execute(
            "DELETE FROM callback_offers WHERE asked_on < ?",
            ((now - timedelta(days=7)).astimezone(LOCAL_TZ).strftime("%Y-%m-%d"),),
        )
        conn.commit()
    finally:
        conn.close()
    when = callback_time(now)
    hhmm = when.strftime("%H:%M")
    if not accepted:
        return False, CONFIRM_NO
    appointments.add_appointment(
        "Rückruf", when, created_by="Senior (Ja am Telefon)", kind="rueckruf", now=now,
    )
    return True, CONFIRM_YES.format(hhmm=hhmm)


def offer_question(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return OFFER_QUESTION.format(hhmm=callback_time(now).strftime("%H:%M"))


def cancel_open_callbacks(now: datetime | None = None) -> int:
    """Cancel planned callbacks ("Rufen Sie mich nicht an")."""
    now = now or datetime.now(timezone.utc)
    conn = connect()
    try:
        deleted = conn.execute(
            "DELETE FROM appointments WHERE kind = 'rueckruf' AND id IN ("
            " SELECT appointment_id FROM reminders WHERE status IN ('geplant', 'klingelt'))"
        ).rowcount
        conn.commit()
        return deleted
    finally:
        conn.close()
