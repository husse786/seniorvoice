#!/usr/bin/env python3
"""Device API for the portal (PR 10).

Decisions of 14.11.2026:
- B4: the portal stores no content. It fetches appointments, reminder status
  and the Help history live from this API, through the device's own tunnel.
  A device that does not answer is shown as "offline seit ..." (A16, A18).
- B5: relatives and Spitex see appointments, reminder status and Help
  events, never conversation content, notes or Rat questions. Admin sees
  technology only. Every appointment shows who entered it; only that person
  may change or delete it, the senior's own appointments nobody else.
- A17: no inbox; Family and Help messages go over the channel (A4).

Rights are checked twice: the portal checks the role, and this API checks
the person against the grant list stored on the device (set up with the
senior's consent, device_api_cli.py). Every request is written to the
access log on the device: who, when, which function, result. No content.

The API listens only on DEVICE_API_HOST (the tunnel address, OA-09 open) and
refuses to start without DEVICE_API_TOKEN_SHA256. Python standard library
only, so nothing extra runs on the senior's device.

Requests: header "Authorization: Bearer <device token>" (the portal) and
"X-Person-Id: <portal account>" (the person using the portal).

    GET    /v1/status                  all roles: reachable, device time
    GET    /v1/appointments            relatives, Spitex
    POST   /v1/appointments            relatives, Spitex: {"title", "due_local", "kind", "pre_minutes"}
    PUT    /v1/appointments/<id>       only who entered it: {"title", "due_local", "pre_minutes"}
    DELETE /v1/appointments/<id>       only who entered it
    GET    /v1/help                    relatives, Spitex with Help visibility
    GET    /v1/advice                  relatives, Spitex: information for the Rat button (B2)
    POST   /v1/advice                  relatives, Spitex: {"topic", "text"}
    PUT    /v1/advice/<id>             only who entered it: {"topic", "text"}
    DELETE /v1/advice/<id>             only who entered it
    GET    /v1/audit                   own entries; admin: all
"""

import hashlib
import hmac
import ipaddress
import json
import re
import sqlite3
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import advice
import appointments
from config import (AUDIT_RETENTION_DAYS, DEVICE_API_HOST, DEVICE_API_PORT,
                    DEVICE_API_TOKEN_SHA256)
from logging_config import get_logger, setup_logging

log = get_logger("device_api")

API_VERSION = "1"
ROLES = ("angehoerige", "spitex", "admin")
CONTENT_ROLES = ("angehoerige", "spitex")      # admin: technology only (B5)
PORTAL_KINDS = ("termin", "medikament")         # callbacks come from conversations (B5)
MAX_BODY = 4096
MAX_TITLE = 200
MAX_PRE_MINUTES = 24 * 60
PERSON_ID = re.compile(r"^[A-Za-z0-9._@-]{1,64}$")
LOCAL_FORMAT = "%Y-%m-%d %H:%M"
MAX_AHEAD_DAYS = 2 * 366
UNAUTH_LOG_SECONDS = 60      # failed tokens: journal warning at most once a minute

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS access_grants (
    person_id    TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    role         TEXT NOT NULL,
    help_visible INTEGER NOT NULL DEFAULT 0,
    granted_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    at           TEXT NOT NULL,
    person_id    TEXT NOT NULL,
    action       TEXT NOT NULL,
    target       TEXT,
    result       INTEGER NOT NULL,
    delete_after TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_person ON audit_log(person_id, at);
"""


_now = appointments._now_utc
_iso = appointments._iso
_schema_ready = False


def _conn() -> sqlite3.Connection:
    global _schema_ready
    conn = appointments.connect()
    if not _schema_ready:
        conn.executescript(_SCHEMA)
        _schema_ready = True
    return conn


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# --- grants (set on the device with the senior's consent, not via the API) ---

def grant(person_id: str, name: str, role: str, help_visible: bool = False) -> None:
    if not PERSON_ID.match(person_id):
        raise ValueError("person id: 1-64 characters A-Z a-z 0-9 . _ @ -")
    if role not in ROLES:
        raise ValueError(f"role must be one of {ROLES}")
    if not name.strip():
        raise ValueError("name is required")
    conn = _conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO access_grants (person_id, name, role, help_visible, granted_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (person_id, name.strip(), role, int(help_visible and role != "admin"), _iso(_now())),
        )
        conn.commit()
    finally:
        conn.close()


def revoke(person_id: str) -> bool:
    conn = _conn()
    try:
        removed = conn.execute("DELETE FROM access_grants WHERE person_id = ?",
                               (person_id,)).rowcount
        conn.commit()
    finally:
        conn.close()
    return removed > 0


def list_grants() -> list[dict]:
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT person_id, name, role, help_visible, granted_at FROM access_grants "
            "ORDER BY role, name").fetchall()
    finally:
        conn.close()
    keys = ("person_id", "name", "role", "help_visible", "granted_at")
    return [dict(zip(keys, r)) for r in rows]


def _get_grant(person_id: str) -> dict | None:
    conn = _conn()
    try:
        row = conn.execute(
            "SELECT person_id, name, role, help_visible FROM access_grants WHERE person_id = ?",
            (person_id,)).fetchone()
    finally:
        conn.close()
    return dict(zip(("person_id", "name", "role", "help_visible"), row)) if row else None


# --- access log on the device (D13): who, when, what, result; no content ---

def audit(person_id: str, action: str, target: str | None, result: int,
          now: datetime | None = None) -> None:
    now = now or _now()
    conn = _conn()
    try:
        conn.execute(
            "INSERT INTO audit_log (at, person_id, action, target, result, delete_after) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (_iso(now), person_id, action, target, result,
             _iso(now + timedelta(days=AUDIT_RETENTION_DAYS))),
        )
        conn.commit()
    finally:
        conn.close()


def list_audit(person_id: str | None = None, limit: int = 200) -> list[dict]:
    conn = _conn()
    try:
        if person_id is None:
            rows = conn.execute(
                "SELECT at, person_id, action, target, result FROM audit_log "
                "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        else:
            rows = conn.execute(
                "SELECT at, person_id, action, target, result FROM audit_log "
                "WHERE person_id = ? ORDER BY id DESC LIMIT ?", (person_id, limit)).fetchall()
    finally:
        conn.close()
    return [dict(zip(("at", "person_id", "action", "target", "result"), r)) for r in rows]


def purge_audit(now: datetime | None = None) -> int:
    now = now or _now()
    conn = _conn()
    try:
        deleted = conn.execute("DELETE FROM audit_log WHERE delete_after <= ?",
                               (_iso(now),)).rowcount
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()
    return deleted


# --- views (only the fields a role may see) ---

def _local(iso_utc: str) -> str:
    return appointments._parse(iso_utc).astimezone(appointments.LOCAL_TZ).strftime(LOCAL_FORMAT)


def _appointment_view(a: dict, person_id: str) -> dict:
    return {
        "id": a["id"],
        "kind": a["kind"],
        "title": a["title"],
        "due_local": _local(a["due_at"]),
        "created_by": a["created_by"],
        "own": a["created_by_id"] == person_id,
        "reminders": [{"stage": r["stage"], "due_local": _local(r["due_at"]),
                       "status": r["status"], "attempts": r["attempts"]}
                      for r in a["reminders"]],
    }


def _help_view() -> list[dict]:
    # No "notified contact": the list may have changed since the alert
    import help_alert
    return [{"id": a["id"], "created_at": a["created_at"], "status": a["status"],
             "delivered": bool(a["delivered"]), "acknowledged_by": a["acknowledged_by"]}
            for a in help_alert.list_alerts()]


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _parse_due(value) -> datetime:
    if not isinstance(value, str):
        raise ApiError(400, "due_local: text \"YYYY-MM-DD HH:MM\"")
    try:
        naive = datetime.strptime(value, LOCAL_FORMAT)
    except ValueError:
        raise ApiError(400, "due_local: \"YYYY-MM-DD HH:MM\"") from None
    due = naive.replace(tzinfo=appointments.LOCAL_TZ)
    roundtrip = due.astimezone(timezone.utc).astimezone(appointments.LOCAL_TZ)
    if roundtrip.replace(tzinfo=None) != naive:
        raise ApiError(400, "due_local does not exist (clock change)")
    if due < _now() - timedelta(minutes=1):
        raise ApiError(400, "due_local is in the past")
    if due > _now() + timedelta(days=MAX_AHEAD_DAYS):
        raise ApiError(400, "due_local is too far ahead")
    return due


def _parse_title(value) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_TITLE:
        raise ApiError(400, f"title: 1-{MAX_TITLE} characters")
    return value.strip()


def _parse_pre(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_PRE_MINUTES:
        raise ApiError(400, f"pre_minutes: 0-{MAX_PRE_MINUTES}")
    return value


# --- HTTP ---

_APPT_ID = re.compile(r"^/v1/appointments/(\d{1,12})$")
_ADVICE_ID = re.compile(r"^/v1/advice/(\d{1,12})$")


class Handler(BaseHTTPRequestHandler):
    server_version = "SeniorVoice"
    sys_version = ""
    protocol_version = "HTTP/1.1"
    timeout = 10
    token_sha256 = ""            # set by make_server()
    started = time.monotonic()
    _last_unauth_log = 0.0

    def log_message(self, fmt, *args):
        pass                     # the access log on the device replaces the HTTP log

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def do_PUT(self):
        self._handle("PUT")

    def do_DELETE(self):
        self._handle("DELETE")

    def _send(self, status: int, payload) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if status >= 400:
            # A body may be left unread: never reuse this connection
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        header = self.headers.get("Authorization", "")
        if not header.startswith("Bearer ") or not self.token_sha256:
            return False
        return hmac.compare_digest(token_hash(header[7:].strip()), self.token_sha256)

    def _body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            raise ApiError(411, "Content-Length required") from None
        if length < 0 or length > MAX_BODY:
            raise ApiError(413, "body too large")
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ApiError(400, "JSON object expected") from None
        if not isinstance(data, dict):
            raise ApiError(400, "JSON object expected")
        return data

    def _handle(self, method: str) -> None:
        path = urlsplit(self.path).path
        match = _APPT_ID.match(path)
        route = "/v1/appointments/{id}" if match else path
        if match is None:
            match = _ADVICE_ID.match(path)
            route = "/v1/advice/{id}" if match else path
        known = route in ("/v1/status", "/v1/audit", "/v1/appointments",
                          "/v1/appointments/{id}", "/v1/help",
                          "/v1/advice", "/v1/advice/{id}")
        action = f"{method} {route if known else '(unknown)'}"
        target = match.group(1) if match else None
        person_id = self.headers.get("X-Person-Id", "").strip()
        if not PERSON_ID.match(person_id):
            person_id = "-"
        status = 500
        try:
            if not self._authorized():
                # Not the portal: nothing is written to the device database
                # (anyone on the network could fill it), only a rare journal line
                now = time.monotonic()
                if now - Handler._last_unauth_log > UNAUTH_LOG_SECONDS:
                    Handler._last_unauth_log = now
                    log.warning("Device API: request without valid token")
                self._send(401, {"error": "unauthorized"})
                return
            person = _get_grant(person_id) if person_id != "-" else None
            if person is None:
                raise ApiError(403, "no access to this device")
            status, payload = self._route(method, route, target, person)
        except ApiError as e:
            status, payload = e.status, {"error": e.message}
        except Exception as e:
            log.error("Device API %s failed: %s", action, type(e).__name__)
            status, payload = 500, {"error": "internal error"}
        try:
            audit(person_id, action[:80], target, status)
        except Exception as e:
            log.error("Access log failed: %s", type(e).__name__)
        self._send(status, payload)

    def _route(self, method: str, route: str, target: str | None, person: dict):
        role = person["role"]
        if (method, route) == ("GET", "/v1/status"):
            return 200, {"api": API_VERSION, "device_time": _iso(_now()),
                         "uptime_s": int(time.monotonic() - self.started)}
        if (method, route) == ("GET", "/v1/audit"):
            return 200, {"entries": list_audit(None if role == "admin" else person["person_id"])}
        known = {("GET", "/v1/appointments"), ("POST", "/v1/appointments"),
                 ("PUT", "/v1/appointments/{id}"), ("DELETE", "/v1/appointments/{id}"),
                 ("GET", "/v1/help"),
                 ("GET", "/v1/advice"), ("POST", "/v1/advice"),
                 ("PUT", "/v1/advice/{id}"), ("DELETE", "/v1/advice/{id}")}
        if (method, route) not in known:
            raise ApiError(404, "not found")
        if role not in CONTENT_ROLES:
            raise ApiError(403, "role has no access to content")
        if route == "/v1/help":
            if not person["help_visible"]:
                raise ApiError(403, "Help history not shared with this person")
            return 200, {"alerts": _help_view()}
        if route.startswith("/v1/advice"):
            return self._advice(method, target, person)
        if method == "GET":
            items = [_appointment_view(a, person["person_id"])
                     for a in appointments.list_appointments() if a["kind"] in PORTAL_KINDS]
            return 200, {"appointments": items}
        if method == "POST":
            data = self._body()
            kind = data.get("kind", "termin")
            if kind not in PORTAL_KINDS:
                raise ApiError(400, f"kind must be one of {PORTAL_KINDS}")
            appt_id = appointments.add_appointment(
                _parse_title(data.get("title")), _parse_due(data.get("due_local")),
                person["name"], kind, _parse_pre(data.get("pre_minutes")),
                created_by_id=person["person_id"])
            return 201, {"id": appt_id}
        existing = appointments.get_appointment(int(target))
        if existing is None or existing["kind"] not in PORTAL_KINDS:
            raise ApiError(404, "not found")
        if existing["created_by_id"] != person["person_id"]:
            raise ApiError(403, "only the person who entered it may change it")
        if method == "DELETE":
            appointments.delete_appointment(existing["id"])
            return 200, {"deleted": existing["id"]}
        data = self._body()
        title = _parse_title(data["title"]) if "title" in data else None
        due = _parse_due(data["due_local"]) if "due_local" in data else None
        if not appointments.update_appointment(existing["id"], title, due,
                                               _parse_pre(data.get("pre_minutes"))):
            raise ApiError(404, "not found")
        return 200, {"id": existing["id"]}


    def _advice(self, method: str, target: str | None, person: dict):
        """Information for the Rat button (B2): read out verbatim on the device."""
        try:
            if method == "GET":
                return 200, {"advice": [_advice_view(i, person["person_id"])
                                        for i in advice.list_items()]}
            if method == "POST":
                data = self._body()
                item_id = advice.add_item(data.get("topic"), data.get("text"),
                                          person["name"], created_by_id=person["person_id"])
                return 201, {"id": item_id}
            existing = advice.get_item(int(target))
            if existing is None:
                raise ApiError(404, "not found")
            if existing["created_by_id"] != person["person_id"]:
                raise ApiError(403, "only the person who entered it may change it")
            if method == "DELETE":
                advice.delete_item(existing["id"])
                return 200, {"deleted": existing["id"]}
            data = self._body()
            if not advice.update_item(existing["id"], data.get("topic"), data.get("text")):
                raise ApiError(404, "not found")
            return 200, {"id": existing["id"]}
        except advice.AdviceError as e:
            raise ApiError(400, str(e)) from None


def _advice_view(item: dict, person_id: str) -> dict:
    return {"id": item["id"], "topic": item["topic"], "text": item["text"],
            "created_by": item["created_by"], "own": item["created_by_id"] == person_id,
            "updated_at": item["updated_at"]}


def _check_host(host: str) -> None:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        raise ValueError("DEVICE_API_HOST must be an IP address (the tunnel address)") from None
    if address.is_unspecified:
        raise ValueError("DEVICE_API_HOST must be the tunnel address, not all interfaces")


def make_server(host: str = DEVICE_API_HOST, port: int = DEVICE_API_PORT,
                token_sha256: str = DEVICE_API_TOKEN_SHA256) -> ThreadingHTTPServer:
    _check_host(host)
    if not re.fullmatch(r"[0-9a-f]{64}", token_sha256 or ""):
        raise ValueError("DEVICE_API_TOKEN_SHA256 missing or invalid (device_api_cli.py token)")
    handler = type("ConfiguredHandler", (Handler,),
                   {"token_sha256": token_sha256, "started": time.monotonic()})
    server = ThreadingHTTPServer((host, port), handler)
    server.daemon_threads = True
    return server


def _purge_loop(stop: threading.Event, interval: float = 3600.0) -> None:
    while not stop.is_set():
        try:
            deleted = purge_audit()
            if deleted:
                log.info("Purge: deleted %d access log entr(ies)", deleted)
        except Exception as e:
            log.error("Access log purge failed: %s", type(e).__name__)
        stop.wait(interval)


def main() -> None:
    setup_logging()
    try:
        server = make_server()
    except (ValueError, OSError) as e:
        log.critical("Device API not started: %s", e)
        sys.exit(1)
    stop = threading.Event()
    threading.Thread(target=_purge_loop, args=(stop,), name="audit-purge", daemon=True).start()
    log.info("Device API listening on %s:%d", DEVICE_API_HOST, DEVICE_API_PORT)
    try:
        server.serve_forever()
    finally:
        stop.set()
        server.server_close()


if __name__ == "__main__":
    main()
