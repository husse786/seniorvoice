#!/usr/bin/env python3
"""SeniorVoice portal (Z7, decision B4): one login, live data from the devices.

- Sign-in with password and second factor (TOTP), session in RAM only.
- Every view fetches its data live from the device over the tunnel and
  passes it on to the browser; nothing of it is stored here (B4). The
  browser never sees a device token.
- Rights are checked twice: here by role and assignment, on the device by its
  own grant list (device_api.py). The portal account login is the person id
  on the device.
- Admin sees technology only (B5): device state and the health view, all
  devices, no content.

Listens on PORTAL_HOST (default 127.0.0.1; with WireGuard the laptop's tunnel
address, never all interfaces). Python standard library only.

    PORTAL_DB=~/seniorvoice-portal/portal.db python server.py
"""

import concurrent.futures
import json
import os
import re
import secrets
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).parent))
from directory import Directory  # noqa: E402

PORTAL_HOST = os.getenv("PORTAL_HOST", "127.0.0.1")
PORTAL_PORT = int(os.getenv("PORTAL_PORT", "8780"))
PORTAL_DB = os.getenv("PORTAL_DB", str(Path.home() / "seniorvoice-portal" / "portal.db"))
# Extra host names the browser may use (e.g. a name for the tunnel address)
PORTAL_ALLOWED_HOSTS = [h.strip() for h in os.getenv("PORTAL_ALLOWED_HOSTS", "").split(",") if h.strip()]
# Set to true once the portal runs behind HTTPS (production, see docs)
PORTAL_SECURE_COOKIE = os.getenv("PORTAL_SECURE_COOKIE", "false").lower() in ("1", "true", "yes")
SESSION_IDLE_SECONDS = int(os.getenv("PORTAL_SESSION_IDLE", "1800"))
DEVICE_TIMEOUT = float(os.getenv("PORTAL_DEVICE_TIMEOUT", "4"))
MAX_BODY = 4096
STATIC = Path(__file__).parent / "static"

CONTENT_ROLES = ("angehoerige", "spitex")
# Allowed proxied calls: (method, path pattern on the device, roles)
_ROUTES = [
    ("GET", r"/v1/appointments", CONTENT_ROLES),
    ("POST", r"/v1/appointments", CONTENT_ROLES),
    ("PUT", r"/v1/appointments/\d{1,12}", CONTENT_ROLES),
    ("DELETE", r"/v1/appointments/\d{1,12}", CONTENT_ROLES),
    ("GET", r"/v1/help", CONTENT_ROLES),
    ("GET", r"/v1/advice", CONTENT_ROLES),
    ("POST", r"/v1/advice", CONTENT_ROLES),
    ("PUT", r"/v1/advice/\d{1,12}", CONTENT_ROLES),
    ("DELETE", r"/v1/advice/\d{1,12}", CONTENT_ROLES),
    ("GET", r"/v1/audit", CONTENT_ROLES + ("admin",)),
    ("GET", r"/v1/health", ("admin",)),
]
_DEVICE_PATH = re.compile(r"^/api/devices/([a-z0-9-]{1,32})(/v1/[a-z]+(?:/\d{1,12})?)$")
_NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class Sessions:
    """In RAM only: a restart of the portal signs everybody out."""

    def __init__(self, idle: int = SESSION_IDLE_SECONDS):
        self.idle = idle
        self._items: dict[str, dict] = {}
        self._lock = threading.Lock()

    def create(self, account: dict) -> str:
        sid = secrets.token_urlsafe(32)
        with self._lock:
            self._items[sid] = {"account": account, "seen": time.monotonic()}
        return sid

    def get(self, sid: str | None) -> dict | None:
        if not sid:
            return None
        with self._lock:
            item = self._items.get(sid)
            if item is None:
                return None
            if time.monotonic() - item["seen"] > self.idle:
                del self._items[sid]
                return None
            item["seen"] = time.monotonic()
            return item["account"]

    def drop(self, sid: str | None) -> None:
        with self._lock:
            self._items.pop(sid or "", None)


def call_device(device: dict, method: str, path: str, person: str,
                body: bytes | None = None) -> tuple[int, dict]:
    """One request to a device API. (0, {...}) when the device does not answer."""
    req = urllib.request.Request(device["api_url"] + path, data=body, method=method)
    req.add_header("Authorization", f"Bearer {device['token']}")
    req.add_header("X-Person-Id", person)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with _NO_PROXY.open(req, timeout=DEVICE_TIMEOUT) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except ValueError:
            return e.code, {"error": "device error"}
    except (urllib.error.URLError, OSError, ValueError):
        return 0, {"error": "offline"}


class Portal:
    def __init__(self, directory: Directory, sessions: Sessions | None = None):
        self.directory = directory
        self.sessions = sessions or Sessions()

    def device_list(self, account: dict) -> list[dict]:
        """Assigned devices with live reachability ("offline seit", A16/A18)."""
        devices = self.directory.devices_for(account)

        def probe(d):
            status, data = call_device(d, "GET", "/v1/status", account["login"])
            if status == 200:
                self.directory.mark_seen(d["id"])
            return d, status, data
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(probe, devices))
        out = []
        for d, status, data in results:
            fresh = self.directory.device(d["id"]) or d
            out.append({"id": d["id"], "label": d["label"], "senior_name": d["senior_name"],
                        "online": status == 200,
                        "no_access": status in (401, 403),
                        "last_seen": fresh["last_seen"],
                        "device_time": data.get("device_time") if status == 200 else None})
        return out

    def proxy(self, account: dict, device_id: str, method: str, path: str,
              body: bytes | None) -> tuple[int, dict]:
        device = next((d for d in self.directory.devices_for(account) if d["id"] == device_id), None)
        if device is None:
            return 404, {"error": "Gerät nicht zugeordnet"}
        allowed = next((roles for m, pattern, roles in _ROUTES
                        if m == method and re.fullmatch(pattern, path)), None)
        if allowed is None:
            return 404, {"error": "unbekannte Funktion"}
        if account["role"] not in allowed:
            return 403, {"error": "für diese Rolle nicht freigegeben"}
        status, data = call_device(device, method, path, account["login"], body)
        if status == 0:
            return 503, {"error": "offline", "last_seen": device["last_seen"]}
        self.directory.mark_seen(device_id)
        return status, data


def make_handler(portal: Portal, allowed_hosts: list[str]):
    class Handler(BaseHTTPRequestHandler):
        server_version = "SeniorVoicePortal"
        sys_version = ""
        protocol_version = "HTTP/1.1"
        timeout = 15

        def log_message(self, fmt, *args):
            pass          # sign-ins are logged in the directory; no request log with ids

        # --- helpers ---

        def _host_ok(self) -> bool:
            host = urlsplit("//" + self.headers.get("Host", "")).hostname or ""
            return host in allowed_hosts

        def _send(self, status: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy",
                             "default-src 'self'; script-src 'self'; style-src 'self'; "
                             "img-src 'self' data:; frame-ancestors 'none'; form-action 'self'")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            if status >= 400:
                self.send_header("Connection", "close")
                self.close_connection = True
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, payload, extra: dict | None = None) -> None:
            self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8", extra)

        def _sid(self) -> str | None:
            for part in self.headers.get("Cookie", "").split(";"):
                k, _, v = part.strip().partition("=")
                if k == "sv_session":
                    return v
            return None

        def _cookie(self, value: str, max_age: int) -> str:
            secure = "; Secure" if PORTAL_SECURE_COOKIE else ""
            return f"sv_session={value}; Path=/; HttpOnly; SameSite=Strict; Max-Age={max_age}{secure}"

        def _body(self) -> bytes:
            length = int(self.headers.get("Content-Length", "0") or 0)
            if not 0 <= length <= MAX_BODY:
                raise ValueError("too large")
            return self.rfile.read(length)

        # --- routing ---

        def do_GET(self):
            self._handle("GET")

        def do_POST(self):
            self._handle("POST")

        def do_PUT(self):
            self._handle("PUT")

        def do_DELETE(self):
            self._handle("DELETE")

        def _handle(self, method: str) -> None:
            if not self._host_ok():
                return self._json(403, {"error": "forbidden"})
            path = urlsplit(self.path).path
            if method == "GET" and not path.startswith("/api/"):
                return self._static(path)
            # Against other web pages: API calls need this header (no simple
            # cross-site request can set it) on top of the SameSite cookie
            if self.headers.get("X-Portal") != "1":
                return self._json(403, {"error": "forbidden"})
            try:
                body = self._body() if method in ("POST", "PUT") else None
            except ValueError:
                return self._json(413, {"error": "zu gross"})
            if (method, path) == ("POST", "/api/login"):
                return self._login(body)
            account = portal.sessions.get(self._sid())
            if account is not None and portal.directory.account(account["login"]) != account:
                portal.sessions.drop(self._sid())     # account removed or role changed
                account = None
            if account is None:
                return self._json(401, {"error": "nicht angemeldet"})
            if (method, path) == ("POST", "/api/logout"):
                portal.sessions.drop(self._sid())
                return self._json(200, {"ok": True}, {"Set-Cookie": self._cookie("", 0)})
            if (method, path) == ("GET", "/api/me"):
                return self._json(200, account)
            if (method, path) == ("GET", "/api/devices"):
                return self._json(200, {"devices": portal.device_list(account)})
            if (method, path) == ("GET", "/api/logins") and account["role"] == "admin":
                return self._json(200, {"entries": portal.directory.login_log()})
            match = _DEVICE_PATH.match(path)
            if match:
                status, data = portal.proxy(account, match.group(1), method, match.group(2), body)
                return self._json(status, data)
            self._json(404, {"error": "not found"})

        def _login(self, body: bytes | None) -> None:
            try:
                data = json.loads(body or b"{}")
                login, password, code = (str(data.get(k, "")) for k in ("login", "password", "code"))
            except (ValueError, AttributeError):
                return self._json(400, {"error": "JSON erwartet"})
            account = portal.directory.check_login(login, password, code)
            if account is None:
                time.sleep(0.5)
                return self._json(401, {"error": "Anmeldung fehlgeschlagen"})
            sid = portal.sessions.create(account)
            self._json(200, account, {"Set-Cookie": self._cookie(sid, SESSION_IDLE_SECONDS)})

        def _static(self, path: str) -> None:
            name = {"/": "index.html"}.get(path, path.lstrip("/"))
            if not re.fullmatch(r"[a-z0-9_-]+\.(html|css|js|svg)", name):
                return self._json(404, {"error": "not found"})
            file = STATIC / name
            if not file.is_file():
                return self._json(404, {"error": "not found"})
            ctype = {"html": "text/html", "css": "text/css", "js": "text/javascript",
                     "svg": "image/svg+xml"}[name.rsplit(".", 1)[1]] + "; charset=utf-8"
            self._send(200, file.read_bytes(), ctype)

    return Handler


def make_server(directory: Directory, host: str = PORTAL_HOST, port: int = PORTAL_PORT,
                allowed_hosts: list[str] | None = None) -> ThreadingHTTPServer:
    if host in ("0.0.0.0", "::", ""):
        raise ValueError("PORTAL_HOST: 127.0.0.1 or the WireGuard address, not all interfaces")
    hosts = ["127.0.0.1", "localhost", host] + (allowed_hosts or PORTAL_ALLOWED_HOSTS)
    server = ThreadingHTTPServer((host, port), make_handler(Portal(directory), hosts))
    server.daemon_threads = True
    return server


def main() -> None:
    directory = Directory(PORTAL_DB)
    try:
        server = make_server(directory)
    except (ValueError, OSError) as e:
        print(f"Portal nicht gestartet: {e}", file=sys.stderr)
        sys.exit(1)

    def purge_loop():
        while True:
            directory.purge()
            time.sleep(3600)
    threading.Thread(target=purge_loop, daemon=True).start()
    print(f"Portal: http://{PORTAL_HOST}:{PORTAL_PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
