"""Help button: notify the contact persons (not an emergency call).

Decisions of 14.11.2026:
- A3: Help is a notification to the stored contact person, not an emergency
  call. The device says "Im Notfall rufen Sie bitte 144 an".
- A4: one channel for Help and Family (channels.py).
- A13: the confirmation is spoken over the speaker (exception to A9) and
  shown large on the screen (PR 11).
- A14: no reaction within 10 minutes -> next contact person. Nobody reacts at
  all -> the device says and shows "Bitte rufen Sie 144 an".
- A15: contacts are an ordered list (default: relatives first, then Spitex),
  maintained in the portal with the senior's consent (contacts CLI until then).
- M7/M13: the message contains no conversation content; Help never goes
  through the LLM and runs in the core process.
- Retention (proposal from 05/06, D9): Help events 30 days.
"""

import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Callable

from appointments import connect, LOCAL_TZ, _iso
from logging_config import get_logger

log = get_logger("help")

ESCALATE_MINUTES = 10          # A14
DELIVERY_GRACE_SECONDS = 60    # confirmed 14.11.: no delivery within 60 s -> say 144
ALERT_RETENTION_DAYS = 30      # D9 proposal

SAY_STARTED = "Ich informiere jetzt {name}. Im Notfall rufen Sie bitte 144 an."
SAY_ALREADY = "Ich habe {name} bereits informiert. Im Notfall rufen Sie bitte 144 an."
SAY_ACK = "{name} hat geantwortet und kümmert sich um Sie."
SAY_NEXT = "{prev} hat noch nicht geantwortet. Ich informiere jetzt {name}."
SAY_CALL_144 = "Ich konnte niemanden erreichen. Bitte rufen Sie 144 an."
SAY_NO_CONTACTS = "Es ist keine Kontaktperson hinterlegt. Bitte rufen Sie 144 an."

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS contacts (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    position  INTEGER NOT NULL,
    name      TEXT NOT NULL,
    role      TEXT NOT NULL,
    address   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS alerts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at      TEXT NOT NULL,
    status          TEXT NOT NULL,
    contact_pos     INTEGER NOT NULL DEFAULT 0,
    notified_at     TEXT,
    delivered       INTEGER NOT NULL DEFAULT 0,
    acknowledged_by TEXT,
    closed_at       TEXT,
    delete_after    TEXT NOT NULL
);
"""

# Alert status values (portal shows them, PR 10)
OFFEN, QUITTIERT, NIEMAND = "offen", "quittiert", "niemand erreicht"


def _conn() -> sqlite3.Connection:
    conn = connect()
    conn.executescript(_SCHEMA)
    return conn


def set_contacts(contacts: list[dict]) -> None:
    """Replace the ordered contact list: [{name, role, address}, ...] (A15)."""
    conn = _conn()
    try:
        conn.execute("DELETE FROM contacts")
        for pos, c in enumerate(contacts):
            conn.execute(
                "INSERT INTO contacts (position, name, role, address) VALUES (?, ?, ?, ?)",
                (pos, c["name"], c["role"], c["address"]),
            )
        conn.commit()
    finally:
        conn.close()


def get_contacts() -> list[dict]:
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT position, name, role, address FROM contacts ORDER BY position"
        ).fetchall()
    finally:
        conn.close()
    return [dict(zip(("position", "name", "role", "address"), r)) for r in rows]


def list_alerts() -> list[dict]:
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT id, created_at, status, contact_pos, delivered, acknowledged_by FROM alerts ORDER BY id"
        ).fetchall()
    finally:
        conn.close()
    keys = ("id", "created_at", "status", "contact_pos", "delivered", "acknowledged_by")
    return [dict(zip(keys, r)) for r in rows]


class HelpService:
    """Runs in the core.

    trigger() is called on the core input thread and never touches the
    database or the network: it only records the request and wakes the
    worker, which creates the alert, sends, polls acknowledgements and
    escalates. Each alert keeps its own copy of the contact list, so editing
    the contacts during an alert cannot break it.
    """

    def __init__(self, channel, announce: Callable[[str], None],
                 senior_name: str = "",
                 now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
                 monotonic: Callable[[], float] = time.monotonic):
        self.channel = channel
        self.announce = announce
        self.senior_name = senior_name
        self.now = now
        self.monotonic = monotonic
        # Re-entrant: helpers close an alert while holding the lock
        self._lock = threading.RLock()
        # {id, contacts, pos, notified_mono, delivered, started_mono, pending_send}
        self._active: dict | None = None
        self._requested = False
        self._recovered = False
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._last_purge = 0.0

    # --- called from the core loop (must not block) ---

    def trigger(self) -> None:
        with self._lock:
            active = self._active
            if active is None:
                self._requested = True
        self._wake.set()
        if active is not None:
            name = active["contacts"][active["pos"]]["name"]
            self.announce(SAY_ALREADY.format(name=name))

    # --- worker: starts alerts, sends, polls acknowledgements, escalates ---

    def step(self) -> None:
        if not self._recovered:
            self._recovered = True
            self._recover_open_alerts()
        with self._lock:
            requested, self._requested = self._requested, False
        if requested:
            self._start()
        if self.monotonic() - self._last_purge > 3600:
            self._last_purge = self.monotonic()
            purge_expired(self.now())
        with self._lock:
            active = None if self._active is None else dict(self._active)
        if active is None:
            self._poll_acks(None)
            return
        contacts = active["contacts"]
        if active["pending_send"]:
            self._send(active)
            with self._lock:
                active = dict(self._active) if self._active else None
            if active is None:
                return
        if self._poll_acks(active):
            return
        now_m = self.monotonic()
        if not active["delivered"] and now_m - active["started_mono"] > DELIVERY_GRACE_SECONDS:
            self._give_up(active)
            return
        if active["notified_mono"] is not None and now_m - active["notified_mono"] >= ESCALATE_MINUTES * 60:
            nxt = active["pos"] + 1
            if nxt < len(contacts):
                with self._lock:
                    # The next contact gets its own delivery deadline
                    self._active.update(pos=nxt, pending_send=True, notified_mono=None,
                                        delivered=False, started_mono=now_m)
                self.announce(SAY_NEXT.format(prev=contacts[active["pos"]]["name"],
                                              name=contacts[nxt]["name"]))
            else:
                self._give_up(active)

    def _start(self) -> None:
        """Create the alert. If that fails, still tell the senior to call 144."""
        try:
            contacts = get_contacts()
            now = self.now()
            conn = _conn()
            try:
                cur = conn.execute(
                    "INSERT INTO alerts (created_at, status, delete_after) VALUES (?, ?, ?)",
                    (_iso(now), OFFEN, _iso(now + timedelta(days=ALERT_RETENTION_DAYS))),
                )
                alert_id = cur.lastrowid
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            log.error("Help alert could not be created: %s", type(e).__name__)
            self.announce(SAY_CALL_144)
            return
        log.warning("HELP pressed (alert %d)", alert_id)
        if not contacts:
            self._close(alert_id, NIEMAND)
            self.announce(SAY_NO_CONTACTS)
            return
        with self._lock:
            self._active = {"id": alert_id, "contacts": contacts, "pos": 0,
                            "notified_mono": None, "delivered": False,
                            "started_mono": self.monotonic(), "pending_send": True}
        self.announce(SAY_STARTED.format(name=contacts[0]["name"]))

    def _recover_open_alerts(self) -> None:
        """After a restart, an alert left 'offen' cannot be followed any more.

        Close it; if it is recent, tell the senior to call 144 (A14), so a
        restart never leaves a Help request silently unanswered.
        """
        now = self.now()
        conn = _conn()
        try:
            rows = conn.execute(
                "SELECT id, created_at FROM alerts WHERE status = ?", (OFFEN,)
            ).fetchall()
        finally:
            conn.close()
        recent = False
        for alert_id, created_at in rows:
            created = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            recent = recent or now - created < timedelta(hours=1)
            self._close(alert_id, NIEMAND)
        if recent:
            self.announce(SAY_CALL_144)

    def _message(self) -> str:
        when = self.now().astimezone(LOCAL_TZ).strftime("%H:%M")
        who = self.senior_name or "Ihr Angehöriger / Ihre Angehörige"
        # No conversation content (M7)
        return (f"SeniorVoice: {who} hat um {when} Uhr den Hilfe-Knopf gedrückt. "
                "Bitte melden Sie sich. Das ist kein Notruf.")

    def _send(self, active: dict) -> None:
        contact = active["contacts"][active["pos"]]
        try:
            self.channel.send_alert(contact["address"], self._message(), active["id"])
        except Exception as e:
            log.error("Help delivery to position %d failed: %s", active["pos"], type(e).__name__)
            return  # retried on the next step
        with self._lock:
            if self._active is None:
                return
            self._active.update(pending_send=False, delivered=True,
                                notified_mono=self.monotonic())
        conn = _conn()
        try:
            conn.execute(
                "UPDATE alerts SET contact_pos = ?, notified_at = ?, delivered = 1 WHERE id = ?",
                (active["pos"], _iso(self.now()), active["id"]),
            )
            conn.commit()
        finally:
            conn.close()

    def _poll_acks(self, active: dict | None) -> bool:
        """Returns True if the active alert was acknowledged."""
        try:
            acks = self.channel.poll_acks()
        except Exception as e:
            log.error("Polling acknowledgements failed: %s", type(e).__name__)
            return False
        if active is None:
            return False  # nothing open: old or unknown acknowledgements are ignored
        contacts = {c["address"]: c for c in active["contacts"]}
        for alert_id, address in acks:
            if alert_id != active["id"] or address not in contacts:
                continue  # unknown sender or old alert: ignored
            name = contacts[address]["name"]
            self._close(alert_id, QUITTIERT, acknowledged_by=name)
            self.announce(SAY_ACK.format(name=name))
            return True
        return False

    def _give_up(self, active: dict) -> None:
        self._close(active["id"], NIEMAND)
        self.announce(SAY_CALL_144)

    def _close(self, alert_id: int, status: str, acknowledged_by: str | None = None) -> None:
        with self._lock:
            if self._active and self._active["id"] == alert_id:
                self._active = None
        conn = _conn()
        try:
            conn.execute(
                "UPDATE alerts SET status = ?, acknowledged_by = ?, closed_at = ? WHERE id = ?",
                (status, acknowledged_by, _iso(self.now()), alert_id),
            )
            conn.commit()
        finally:
            conn.close()
        log.warning("Help alert %d closed: %s", alert_id, status)

    def run_worker(self, interval: float = 2.0) -> threading.Thread:
        def loop():
            while not self._stop.is_set():
                try:
                    self.step()
                except Exception as e:
                    log.error("Help worker error: %s", type(e).__name__)
                self._wake.wait(interval)   # a Help press wakes the worker at once
                self._wake.clear()
        thread = threading.Thread(target=loop, name="help", daemon=True)
        thread.start()
        return thread

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def is_open(self) -> bool:
        """An alert is running (shown on the simulated phone page)."""
        with self._lock:
            return self._active is not None or self._requested

    def simulate_ack(self) -> None:
        """Keyboard simulation: current contact presses "Ich kümmere mich"."""
        with self._lock:
            active = dict(self._active) if self._active else None
        if active and hasattr(self.channel, "simulate_ack"):
            self.channel.simulate_ack(active["id"], active["contacts"][active["pos"]]["address"])
        self._wake.set()


def purge_expired(now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    conn = _conn()
    try:
        n = conn.execute("DELETE FROM alerts WHERE delete_after <= ?", (_iso(now),)).rowcount
        conn.commit()
        return n
    finally:
        conn.close()
