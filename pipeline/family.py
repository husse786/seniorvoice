"""Family button: a spoken message to the family (decision A4, M7, D8).

Flow (dialog process): "Was möchten Sie Ihrer Familie sagen?" -> the senior
speaks -> the device reads it back -> only after a clear "Ja" the text goes
into the outbox. The core process sends it over the same channel as Help (A4).

Retention (D8): the text stays on the device at most 7 days, also if it could
never be sent; after sending, the text is removed and only the status stays
(7 days after delivery). Replies to the device are an outlook (A4).
Recipient (confirmed 14.11.2026): the first contact in the Help list that is not Spitex.
"""

import threading
import time
from datetime import datetime, timedelta, timezone

from appointments import connect, _iso
from logging_config import get_logger

log = get_logger("family")

TEXT_DAYS = 7

ASK = "Was möchten Sie Ihrer Familie sagen? Sprechen Sie nach dem Ton."
READ_BACK = "Ich habe verstanden: {text}. Soll ich das an {name} senden? Bitte sagen Sie Ja oder Nein."
SENT = "In Ordnung. Ich sende die Nachricht an {name}."
NOT_SENT = "In Ordnung, ich sende nichts."
NOTHING_HEARD = "Ich habe nichts verstanden. Drücken Sie bitte nochmals auf Familie."
NO_RECIPIENT = "Es ist niemand aus der Familie hinterlegt."
LIFT_HANDSET = "Bitte heben Sie zuerst den Hörer ab und drücken Sie dann auf Familie."

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS outbox (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    address     TEXT NOT NULL,
    name        TEXT NOT NULL,
    text        TEXT NOT NULL,
    status      TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    sent_at     TEXT,
    delete_after TEXT NOT NULL
);
"""
WARTET, GESENDET, NICHT_GESENDET = "wartet", "gesendet", "nicht gesendet"


def _conn():
    conn = connect()
    conn.executescript(_SCHEMA)
    return conn


def recipient() -> dict | None:
    from help_alert import get_contacts
    for c in get_contacts():
        if c["role"].strip().lower() != "spitex":
            return c
    return None


def queue_message(text: str, contact: dict, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    conn = _conn()
    try:
        cur = conn.execute(
            "INSERT INTO outbox (address, name, text, status, created_at, delete_after) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (contact["address"], contact["name"], text, WARTET, _iso(now),
             _iso(now + timedelta(days=TEXT_DAYS))),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_outbox() -> list[dict]:
    conn = _conn()
    try:
        rows = conn.execute("SELECT id, name, text, status FROM outbox ORDER BY id").fetchall()
    finally:
        conn.close()
    return [dict(zip(("id", "name", "text", "status"), r)) for r in rows]


# A removed text may still sit in the WAL until a checkpoint succeeds
_checkpoint_due = False


def _truncate_wal(conn) -> None:
    global _checkpoint_due
    from memory import _checkpoint_truncate
    _checkpoint_due = not _checkpoint_truncate(conn)


def send_pending(channel, now: datetime | None = None) -> int:
    """Send waiting messages; afterwards keep only the status (D8).

    Expired messages (older than 7 days) are never sent. Each sent message is
    committed on its own, so no write lock is held during network requests.
    """
    now = now or datetime.now(timezone.utc)
    conn = _conn()
    sent = 0
    try:
        rows = conn.execute(
            "SELECT id, address, text FROM outbox WHERE status = ? AND delete_after > ?",
            (WARTET, _iso(now)),
        ).fetchall()
        for msg_id, address, text in rows:
            try:
                channel.send_message(address, f"Nachricht über SeniorVoice: {text}")
            except Exception as e:
                log.error("Family message %d not sent: %s", msg_id, type(e).__name__)
                continue
            conn.execute(
                "UPDATE outbox SET status = ?, text = '', sent_at = ?, delete_after = ? WHERE id = ?",
                (GESENDET, _iso(now), _iso(now + timedelta(days=TEXT_DAYS)), msg_id),
            )
            conn.commit()
            sent += 1
        if sent or _checkpoint_due:
            _truncate_wal(conn)
    finally:
        conn.close()
    return sent


def purge_expired(now: datetime | None = None) -> int:
    """Delete rows past their date (unsent text too: max 7 days, D8)."""
    now = now or datetime.now(timezone.utc)
    conn = _conn()
    try:
        n = conn.execute("DELETE FROM outbox WHERE delete_after <= ?", (_iso(now),)).rowcount
        conn.commit()
        if n or _checkpoint_due:
            _truncate_wal(conn)
        return n
    finally:
        conn.close()


def run_sender(channel, interval: float = 5.0) -> threading.Thread:
    """Core-side worker: sends the outbox and purges old rows.

    A blocked WAL checkpoint is retried on every round until it succeeds.
    """
    def loop():
        last_purge = 0.0
        while True:
            try:
                send_pending(channel)
                if _checkpoint_due or time.monotonic() - last_purge > 3600:
                    last_purge = time.monotonic()
                    purge_expired()
            except Exception as e:
                log.error("Outbox worker error: %s", type(e).__name__)
            time.sleep(interval)
    thread = threading.Thread(target=loop, name="outbox", daemon=True)
    thread.start()
    return thread
