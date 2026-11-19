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
- Cancel (T13, Husey 19.11.2026, accidental presses in tests): the notice waits
  CANCEL_SECONDS before it is sent. A second press in that time cancels it,
  so nobody was told and no all-clear is needed. A press less than
  CANCEL_IGNORE_SECONDS after the previous press is ignored, so pressing
  again and again in panic never cancels (nor toggles after a cancel). Within
  NO_CANCEL_AFTER_CANCEL_SECONDS after a cancel the next press is sent at
  once and cannot be cancelled. A cancelled
  alert stays in the Help history as "abgebrochen" and never comes back after
  a restart.
"""

import math
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
CANCEL_SECONDS = 10            # second press within this time cancels (before sending)
CANCEL_IGNORE_SECONDS = 2      # a press this soon after the previous press is ignored
CANCEL_MIN_WINDOW_SECONDS = 5  # if the worker starts late, still this long to cancel
NO_CANCEL_AFTER_CANCEL_SECONDS = 120   # after a cancel, the next press goes out at once
CANCELLED_SHOWN_SECONDS = 10   # screen shows "abgebrochen" this long

SAY_STARTED = "Ich informiere jetzt {name}. Im Notfall rufen Sie bitte 144 an."
SAY_HOLD = "Ich informiere gleich {name}. Falls das ein Versehen war, drücken Sie nochmals Hilfe."
SAY_SENT = "Ich habe {name} informiert. Im Notfall rufen Sie bitte 144 an."
SAY_CANCELLED = ("Abgebrochen. Es wird niemand informiert. "
                 "Wenn Sie doch Hilfe brauchen, drücken Sie nochmals Hilfe.")
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
OFFEN, QUITTIERT, NIEMAND, ABGEBROCHEN = "offen", "quittiert", "niemand erreicht", "abgebrochen"


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
        # {id, contacts, pos, notified_mono, delivered, started_mono, pending_send,
        #  pressed_mono, held, send_after}
        self._active: dict | None = None
        self._requested = False
        self._request_mono = 0.0          # when the pending request was pressed
        self._request_cancellable = True
        self._cancel_requested = False
        self._last_cancel_mono: float | None = None
        self._last_press_mono: float | None = None
        self._recovered = False
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._last_purge = 0.0

    # --- called from the core loop (must not block) ---

    def trigger(self) -> None:
        now = self.monotonic()
        say = None
        with self._lock:
            gap = None if self._last_press_mono is None else now - self._last_press_mono
            self._last_press_mono = now
            active = self._active
            if gap is not None and gap < CANCEL_IGNORE_SECONDS:
                return      # repeated pressing (panic, bounce): never cancels, never toggles
            if active is None and not self._requested:
                self._requested = True
                self._request_mono = now
                self._request_cancellable = (
                    self._last_cancel_mono is None
                    or now - self._last_cancel_mono >= NO_CANCEL_AFTER_CANCEL_SECONDS)
            elif self._can_cancel(now):
                self._cancel_requested = True
            elif active is not None and not active["held"]:
                say = SAY_ALREADY.format(name=active["contacts"][active["pos"]]["name"])
            # otherwise (the window has passed but sending has not begun yet,
            # or a cancel is already asked): ignored
        self._wake.set()
        if say:
            self.announce(say)

    def _can_cancel(self, now: float) -> bool:
        """This press cancels the waiting notice (call with the lock held).

        _requested stays set until _start() has set _active, so a press while
        the alert is being created is also a cancel, never a second alert.
        """
        if self._cancel_requested:
            return False
        active = self._active
        if active is not None:
            return bool(active["held"]) and now < active["send_after"]
        if self._requested and self._request_cancellable:
            return now < self._request_mono + CANCEL_SECONDS
        return False

    # --- worker: starts alerts, sends, polls acknowledgements, escalates ---

    def step(self) -> None:
        if not self._recovered:
            self._recovered = True
            self._recover_open_alerts()
        with self._lock:
            # _requested is cleared in _start(), together with setting _active
            requested = self._requested and self._active is None
            pressed, cancellable = self._request_mono, self._request_cancellable
        if requested:
            self._start(pressed, cancellable)
        cancelled_id = None
        with self._lock:
            cancel, self._cancel_requested = self._cancel_requested, False
            held = self._active if self._active and self._active["held"] else None
            if held and cancel:
                # Off the active slot at once: a later press is a new request
                cancelled_id = held["id"]
                self._active = None
                self._last_cancel_mono = self.monotonic()
            elif held and self.monotonic() >= held["send_after"]:
                # The wait ends under the lock: from then on a press can no
                # longer cancel, so trigger() and the send cannot race
                held["held"] = False
        if cancelled_id is not None:
            self._cancel(cancelled_id)
        if self.monotonic() - self._last_purge > 3600:
            self._last_purge = self.monotonic()
            purge_expired(self.now())
        with self._lock:
            active = None if self._active is None else dict(self._active)
        if active is None:
            self._poll_acks(None)
            return
        contacts = active["contacts"]
        if active["held"]:
            return                      # waiting: a second press may still cancel
        if active["pending_send"]:
            first = active["pos"] == 0 and not active["delivered"]
            self._send(active)
            with self._lock:
                sent_now = (first and self._active is not None
                            and self._active["id"] == active["id"]
                            and self._active["delivered"] and self._active["announce_sent"])
                if sent_now:
                    self._active["announce_sent"] = False
            if sent_now:
                # After the wait, say that the notice is out now (A13)
                self.announce(SAY_SENT.format(name=contacts[0]["name"]))
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

    def _start(self, pressed_mono: float, cancellable: bool) -> None:
        """Create the alert. If that fails, still tell the senior to call 144.

        cancellable: the notice waits until CANCEL_SECONDS after the press, so
        a second press can still cancel it. False right after a cancel.
        """
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
            with self._lock:
                self._requested = False
            self.announce(SAY_CALL_144)
            return
        log.warning("HELP pressed (alert %d)", alert_id)
        if not contacts:
            with self._lock:
                self._requested = False
            self._close(alert_id, NIEMAND)
            self.announce(SAY_NO_CONTACTS)
            return
        now_m = self.monotonic()
        # Worker late (slow database, mail poll): the senior still gets time
        # to cancel after hearing the announcement
        send_after = (max(pressed_mono + CANCEL_SECONDS, now_m + CANCEL_MIN_WINDOW_SECONDS)
                      if cancellable else now_m)
        with self._lock:
            self._requested = False
            # The delivery deadline (DELIVERY_GRACE_SECONDS) starts when sending may begin
            self._active = {"id": alert_id, "contacts": contacts, "pos": 0,
                            "notified_mono": None, "delivered": False,
                            "started_mono": max(send_after, self.monotonic()),
                            "pending_send": True, "pressed_mono": pressed_mono,
                            "held": cancellable, "send_after": send_after,
                            "announce_sent": cancellable}
        name = contacts[0]["name"]
        self.announce((SAY_HOLD if cancellable else SAY_STARTED).format(name=name))

    def _cancel(self, alert_id: int) -> None:
        """Second press while the notice waits: nobody has been told."""
        self._close(alert_id, ABGEBROCHEN)
        self.announce(SAY_CANCELLED)

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
        # E-mail addresses are not case sensitive (F4); chat ids are digits
        contacts = {c["address"].strip().lower(): c for c in active["contacts"]}
        for alert_id, address in acks:
            address = str(address).strip().lower()
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
                # A Help press wakes the worker at once; while the notice
                # waits, wake exactly when it is due
                self._wake.wait(self._wait_time(interval))
                self._wake.clear()
        thread = threading.Thread(target=loop, name="help", daemon=True)
        thread.start()
        return thread

    def _wait_time(self, interval: float) -> float:
        with self._lock:
            active = self._active
            if active is None or not active["held"]:
                return interval
            due = active["send_after"] - self.monotonic()
        return min(interval, max(0.05, due))

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def screen_status(self) -> dict | None:
        """Who is told, for the device screen (A13). None if nothing to show.

        phase: "wartet" (a second press still cancels, rest = seconds left),
        "unterwegs" (sending or sent) or "abgebrochen" (cancelled just now).
        """
        now = self.monotonic()
        with self._lock:
            active = self._active
            if active is None:
                if self._requested:
                    rest = max(0, math.ceil(self._request_mono + CANCEL_SECONDS - now))
                    return {"kontakt": "", "rolle": "", "zugestellt": False,
                            "phase": "wartet" if self._request_cancellable else "unterwegs",
                            "rest": rest if self._request_cancellable else 0}
                if self._recently_cancelled(now):
                    return {"kontakt": "", "rolle": "", "zugestellt": False,
                            "phase": "abgebrochen", "rest": 0}
                return None
            contact = active["contacts"][active["pos"]]
            held = bool(active["held"])
            rest = max(0, math.ceil(active["send_after"] - now)) if held else 0
            return {"kontakt": contact.get("name", ""), "rolle": contact.get("role", ""),
                    "zugestellt": bool(active.get("delivered")),
                    "phase": "wartet" if held else "unterwegs", "rest": rest}

    def _recently_cancelled(self, now: float) -> bool:
        return (self._last_cancel_mono is not None
                and now - self._last_cancel_mono < CANCELLED_SHOWN_SECONDS)

    def is_open(self) -> bool:
        """An alert is running (shown on the simulated phone page)."""
        with self._lock:
            return self._active is not None or self._requested

    def phase(self) -> str | None:
        """For the simulated phone page: None, "wartet", "unterwegs", "abgebrochen"."""
        status = self.screen_status()
        return status["phase"] if status else None

    def simulate_ack(self) -> None:
        """Keyboard simulation: current contact presses "Ich kümmere mich"."""
        with self._lock:
            active = dict(self._active) if self._active else None
        # Nothing has been sent while the notice waits: nobody can answer yet
        if active and not active["held"] and hasattr(self.channel, "simulate_ack"):
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
