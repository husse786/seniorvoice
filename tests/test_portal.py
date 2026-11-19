"""Portal (Z7, B4, B5): sign-in with second factor, live data from the device,
rights by role and assignment, nothing of the content stored in the portal."""

import json
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "portal"))
import directory as directory_mod  # noqa: E402
import server as portal_server  # noqa: E402

ZH = ZoneInfo("Europe/Zurich")
TOKEN = "device-token-abc"
PW = "ein-langes-passwort"


class Browser:
    """Keeps the session cookie like a browser does."""

    def __init__(self, base):
        self.base = base
        self.cookie = None
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def call(self, method, path, body=None, portal_header=True, host=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=data, method=method)
        if portal_header:
            req.add_header("X-Portal", "1")
        if self.cookie:
            req.add_header("Cookie", self.cookie)
        if host:
            req.add_header("Host", host)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with self.opener.open(req, timeout=10) as resp:
                status, headers, raw = resp.status, resp.headers, resp.read()
        except urllib.error.HTTPError as e:
            status, headers, raw = e.code, e.headers, e.read()
        cookie = headers.get("Set-Cookie")
        if cookie:
            self.cookie = cookie.split(";", 1)[0]
        try:
            return status, json.loads(raw)
        except ValueError:
            return status, raw.decode("utf-8", "replace")

    def login(self, login, secret, password=PW):
        return self.call("POST", "/api/login", {
            "login": login, "password": password,
            "code": directory_mod.totp(secret, time.time())})


@pytest.fixture
def setup(env, tmp_path):
    device_api = env.load("device_api")
    dev = device_api.make_server("127.0.0.1", 0, device_api.token_hash(TOKEN))
    threading.Thread(target=dev.serve_forever, daemon=True).start()
    device_api.grant("sandra", "Sandra Keller", "angehoerige", help_visible=True)
    device_api.grant("mueller", "M. Müller", "spitex")
    device_api.grant("team", "Projektteam", "admin")

    d = directory_mod.Directory(tmp_path / "portal" / "portal.db")
    secrets_ = {
        "sandra": d.add_account("sandra", "Sandra Keller", "angehoerige", PW),
        "mueller": d.add_account("mueller", "M. Müller", "spitex", PW),
        "team": d.add_account("team", "Projektteam", "admin", PW),
        "fremd": d.add_account("fremd", "Andere Person", "angehoerige", PW),
    }
    d.add_device("keller", "Telefon Frau Keller", "Frau Keller",
                 f"http://127.0.0.1:{dev.server_address[1]}", TOKEN)
    d.add_device("weg", "Telefon offline", "Herr Weg", "http://127.0.0.1:9", "x")
    d.assign("sandra", "keller")
    d.assign("mueller", "keller")
    d.assign("mueller", "weg")

    srv = portal_server.make_server(d, "127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    yield {"base": base, "dir": d, "secrets": secrets_, "device_api": device_api,
           "appointments": __import__("appointments"), "tmp": tmp_path}
    srv.shutdown()
    srv.server_close()
    dev.shutdown()
    dev.server_close()


def _future(minutes=180):
    return (datetime.now(ZH) + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M")


# --- directory ---

def test_directory_file_is_private_and_passwords_hashed(setup):
    path = setup["tmp"] / "portal" / "portal.db"
    assert path.stat().st_mode & 0o077 == 0
    raw = path.read_bytes()
    assert PW.encode() not in raw


def test_totp_matches_rfc6238_vector():
    # RFC 6238 appendix B, SHA1, secret "12345678901234567890", T = 59 s -> 94287082
    import base64
    secret = base64.b32encode(b"12345678901234567890").decode()
    assert directory_mod.totp(secret, 59, digits=8) == "94287082"


def test_login_needs_password_and_code_and_locks(setup):
    d, s = setup["dir"], setup["secrets"]["sandra"]
    now = time.time()
    assert d.check_login("sandra", PW, "000000", now) is None
    assert d.check_login("sandra", "falsch-falsch", directory_mod.totp(s, now), now) is None
    assert d.check_login("sandra", PW, directory_mod.totp(s, now), now)["role"] == "angehoerige"
    for _ in range(5):
        d.check_login("sandra", "falsch-falsch", "000000", now)
    assert d.check_login("sandra", PW, directory_mod.totp(s, now), now) is None     # locked
    later = now + directory_mod.LOCK_SECONDS + 1
    assert d.check_login("sandra", PW, directory_mod.totp(s, later), later) is not None
    results = [e["result"] for e in d.login_log()]
    assert "gesperrt" in results and "falsch" in results


def test_angehoerige_get_exactly_one_device(setup):
    d = setup["dir"]
    with pytest.raises(directory_mod.DirectoryError):
        d.assign("sandra", "weg")
    with pytest.raises(directory_mod.DirectoryError):
        d.assign("team", "keller")         # admin sees all, technology only


# --- server ---

def test_api_needs_session_and_portal_header(setup):
    b = Browser(setup["base"])
    assert b.call("GET", "/api/devices")[0] == 401
    assert b.login("sandra", setup["secrets"]["sandra"])[0] == 200
    assert b.call("GET", "/api/devices", portal_header=False)[0] == 403
    assert b.call("GET", "/api/devices", host="evil.example")[0] == 403
    assert b.call("GET", "/api/devices")[0] == 200
    b.call("POST", "/api/logout")
    assert b.call("GET", "/api/devices")[0] == 401


def test_cookie_is_httponly_samesite(setup):
    req = urllib.request.Request(setup["base"] + "/api/login", method="POST", data=json.dumps({
        "login": "sandra", "password": PW,
        "code": directory_mod.totp(setup["secrets"]["sandra"], time.time())}).encode())
    req.add_header("X-Portal", "1")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=10) as resp:
        cookie = resp.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Strict" in cookie


def test_refuses_all_interfaces(setup):
    with pytest.raises(ValueError):
        portal_server.make_server(setup["dir"], "0.0.0.0", 0)


def test_device_list_shows_online_and_offline(setup):
    b = Browser(setup["base"])
    b.login("mueller", setup["secrets"]["mueller"])
    status, body = b.call("GET", "/api/devices")
    by_id = {x["id"]: x for x in body["devices"]}
    assert by_id["keller"]["online"] and by_id["keller"]["last_seen"]
    assert not by_id["weg"]["online"] and by_id["weg"]["last_seen"] is None
    assert all("token" not in x and "api_url" not in x for x in body["devices"])


def test_z7_appointment_from_portal_lands_on_device(setup):
    b = Browser(setup["base"])
    b.login("sandra", setup["secrets"]["sandra"])
    status, body = b.call("POST", "/api/devices/keller/v1/appointments",
                          {"title": "Arzt Dr. Meier", "due_local": _future(), "kind": "termin"})
    assert status == 201
    items = setup["appointments"].list_appointments()
    assert [a["title"] for a in items] == ["Arzt Dr. Meier"]
    assert items[0]["created_by"] == "Sandra Keller"
    # Spitex sees it, may not delete it (B5)
    m = Browser(setup["base"])
    m.login("mueller", setup["secrets"]["mueller"])
    status, body = m.call("GET", "/api/devices/keller/v1/appointments")
    appt = body["appointments"][0]
    assert appt["own"] is False
    assert m.call("DELETE", f"/api/devices/keller/v1/appointments/{appt['id']}")[0] == 403
    assert b.call("DELETE", f"/api/devices/keller/v1/appointments/{appt['id']}")[0] == 200


def test_not_assigned_device_is_refused(setup):
    b = Browser(setup["base"])
    b.login("fremd", setup["secrets"]["fremd"])
    assert b.call("GET", "/api/devices")[1]["devices"] == []
    assert b.call("GET", "/api/devices/keller/v1/appointments")[0] == 404


def test_admin_technology_only(setup):
    b = Browser(setup["base"])
    b.login("team", setup["secrets"]["team"])
    assert b.call("GET", "/api/devices/keller/v1/appointments")[0] == 403
    assert b.call("GET", "/api/devices/keller/v1/help")[0] == 403
    status, body = b.call("GET", "/api/devices/keller/v1/health")
    assert status == 200 and "daily" in body and "ai" in body
    assert b.call("GET", "/api/logins")[0] == 200
    s = Browser(setup["base"])
    s.login("sandra", setup["secrets"]["sandra"])
    assert s.call("GET", "/api/devices/keller/v1/health")[0] == 403
    assert s.call("GET", "/api/logins")[0] == 404


def test_offline_device_gives_503_with_last_seen(setup):
    b = Browser(setup["base"])
    b.login("mueller", setup["secrets"]["mueller"])
    status, body = b.call("GET", "/api/devices/weg/v1/appointments")
    assert status == 503 and body["error"] == "offline"


def test_unknown_paths_are_not_forwarded(setup):
    b = Browser(setup["base"])
    b.login("sandra", setup["secrets"]["sandra"])
    for path in ("/api/devices/keller/v1/../v1/health", "/api/devices/keller/v2/x",
                 "/api/devices/keller/v1/appointments/1/x"):
        assert b.call("GET", path)[0] == 404


def test_removed_account_loses_session(setup):
    b = Browser(setup["base"])
    b.login("sandra", setup["secrets"]["sandra"])
    setup["dir"].remove_account("sandra")
    assert b.call("GET", "/api/devices")[0] == 401


def test_portal_stores_no_content(setup):
    b = Browser(setup["base"])
    b.login("sandra", setup["secrets"]["sandra"])
    b.call("POST", "/api/devices/keller/v1/appointments",
           {"title": "Geheimer Arzttermin XYZ", "due_local": _future(), "kind": "termin"})
    b.call("POST", "/api/devices/keller/v1/advice", {"topic": "Blutdruck", "text": "Inhalt QWERTZ"})
    b.call("GET", "/api/devices/keller/v1/appointments")
    portal_dir = setup["tmp"] / "portal"
    for f in portal_dir.rglob("*"):
        if f.is_file():
            raw = f.read_bytes()
            assert b"XYZ" not in raw and b"QWERTZ" not in raw
    conn = sqlite3.connect(portal_dir / "portal.db")
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert tables <= {"accounts", "devices", "assignments", "login_log", "sqlite_sequence"}


def test_static_files_and_security_headers(setup):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(setup["base"] + "/", timeout=10) as resp:
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert "default-src 'self'" in resp.headers["Content-Security-Policy"]
        assert b"SeniorVoice Portal" in resp.read()
    for path in ("/app.js", "/app.css"):
        with opener.open(setup["base"] + path, timeout=10) as resp:
            assert resp.status == 200
    with pytest.raises(urllib.error.HTTPError):
        opener.open(setup["base"] + "/../server.py", timeout=10)
