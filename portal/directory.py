"""Directory of the portal (D16): the only data the portal keeps.

Decision B4 (14.11.2026): the portal stores no content of the seniors. It
keeps accounts (password as a hash, second factor), roles, which person may
see which device (and that device's address and token), when a device last
answered ("offline seit", A18), and a log of sign-ins. Appointments, Help
events, Rat information and the access log stay on the devices and are
fetched live on every view.

Python standard library only: scrypt for passwords, TOTP (RFC 6238) for the
second factor. The database file is created readable for its owner only,
because it holds the device tokens.
"""

import base64
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import struct
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROLES = ("angehoerige", "spitex", "admin")
# Same rule as the person id on the device (device_api.PERSON_ID)
LOGIN = re.compile(r"^[A-Za-z0-9._@-]{1,64}$")
DEVICE_ID = re.compile(r"^[a-z0-9-]{1,32}$")
LOGIN_LOG_DAYS = 30          # proposal, like the access log on the device (DS-07 open)
MAX_FAILED = 5
LOCK_SECONDS = 300
MIN_PASSWORD = 10

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS accounts (
    login        TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    role         TEXT NOT NULL,
    pw_hash      TEXT NOT NULL,
    totp_secret  TEXT NOT NULL,
    failed       INTEGER NOT NULL DEFAULT 0,
    locked_until REAL NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS devices (
    id           TEXT PRIMARY KEY,
    label        TEXT NOT NULL,
    senior_name  TEXT NOT NULL,
    api_url      TEXT NOT NULL,
    token        TEXT NOT NULL,
    last_seen    TEXT
);
CREATE TABLE IF NOT EXISTS assignments (
    login        TEXT NOT NULL REFERENCES accounts(login) ON DELETE CASCADE,
    device_id    TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    PRIMARY KEY (login, device_id)
);
CREATE TABLE IF NOT EXISTS login_log (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    at     TEXT NOT NULL,
    login  TEXT NOT NULL,
    result TEXT NOT NULL
);
"""


class DirectoryError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class Directory:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            # Owner only: the file holds the device tokens
            fd = os.open(self.path, os.O_CREAT | os.O_WRONLY, 0o600)
            os.close(fd)
        conn = self._conn()
        conn.executescript(_SCHEMA)
        conn.close()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), timeout=5.0)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # --- accounts ---

    def add_account(self, login: str, name: str, role: str, password: str) -> str:
        """Creates the account; returns the TOTP secret for the authenticator app."""
        if not LOGIN.match(login):
            raise DirectoryError("Login: 1-64 Zeichen A-Z a-z 0-9 . _ @ -")
        if role not in ROLES:
            raise DirectoryError(f"Rolle: {', '.join(ROLES)}")
        if not name.strip():
            raise DirectoryError("Name fehlt")
        if len(password) < MIN_PASSWORD:
            raise DirectoryError(f"Passwort: mindestens {MIN_PASSWORD} Zeichen")
        secret = base64.b32encode(secrets.token_bytes(20)).decode("ascii")
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO accounts (login, name, role, pw_hash, totp_secret, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (login, name.strip(), role, hash_password(password), secret, _iso(_now())))
            conn.commit()
        except sqlite3.IntegrityError:
            raise DirectoryError("Login existiert schon") from None
        finally:
            conn.close()
        return secret

    def remove_account(self, login: str) -> bool:
        conn = self._conn()
        try:
            n = conn.execute("DELETE FROM accounts WHERE login = ?", (login,)).rowcount
            conn.commit()
        finally:
            conn.close()
        return n > 0

    def account(self, login: str) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT login, name, role FROM accounts WHERE login = ?",
                               (login,)).fetchone()
        finally:
            conn.close()
        return dict(zip(("login", "name", "role"), row)) if row else None

    def accounts(self) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute("SELECT login, name, role FROM accounts ORDER BY role, login").fetchall()
        finally:
            conn.close()
        return [dict(zip(("login", "name", "role"), r)) for r in rows]

    def check_login(self, login: str, password: str, code: str,
                    now: float | None = None) -> dict | None:
        """Password and second factor. Locks the account for a while after
        repeated failures. Every attempt is logged (who, when, result)."""
        now = now or time.time()
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT pw_hash, totp_secret, failed, locked_until, name, role FROM accounts "
                "WHERE login = ?",
                (login,)).fetchone() if LOGIN.match(login or "") else None
            if row is None:
                verify_password(password, _DUMMY_HASH)          # same time as a real check
                self._log(conn, login if LOGIN.match(login or "") else "-", "unbekannt")
                return None
            pw_hash, secret, failed, locked_until, name, role = row
            if locked_until > now:
                self._log(conn, login, "gesperrt")
                return None
            if verify_password(password, pw_hash) and verify_totp(secret, code, now):
                conn.execute("UPDATE accounts SET failed = 0, locked_until = 0 WHERE login = ?",
                             (login,))
                self._log(conn, login, "ok")
                return {"login": login, "name": name, "role": role}
            failed += 1
            locked = now + LOCK_SECONDS if failed >= MAX_FAILED else 0
            conn.execute("UPDATE accounts SET failed = ?, locked_until = ? WHERE login = ?",
                         (0 if locked else failed, locked, login))
            self._log(conn, login, "falsch")
            return None
        finally:
            conn.commit()
            conn.close()

    def _log(self, conn, login: str, result: str) -> None:
        conn.execute("INSERT INTO login_log (at, login, result) VALUES (?, ?, ?)",
                     (_iso(_now()), login, result))

    def login_log(self, limit: int = 200) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute("SELECT at, login, result FROM login_log ORDER BY id DESC LIMIT ?",
                                (limit,)).fetchall()
        finally:
            conn.close()
        return [dict(zip(("at", "login", "result"), r)) for r in rows]

    def purge(self, now: datetime | None = None) -> int:
        cutoff = _iso((now or _now()) - timedelta(days=LOGIN_LOG_DAYS))
        conn = self._conn()
        try:
            n = conn.execute("DELETE FROM login_log WHERE at < ?", (cutoff,)).rowcount
            conn.commit()
        finally:
            conn.close()
        return n

    # --- devices and assignments ---

    def add_device(self, device_id: str, label: str, senior_name: str,
                   api_url: str, token: str) -> None:
        if not DEVICE_ID.match(device_id):
            raise DirectoryError("Geräte-ID: 1-32 Zeichen a-z 0-9 -")
        if not re.match(r"^http://[0-9a-zA-Z.\[\]:]+(:\d+)?$", api_url):
            raise DirectoryError("Adresse wie http://10.77.0.2:8770 (Tunnel-Adresse des Geräts)")
        if not token.strip() or not label.strip() or not senior_name.strip():
            raise DirectoryError("Bezeichnung, Name und Token sind nötig")
        conn = self._conn()
        try:
            conn.execute("INSERT OR REPLACE INTO devices (id, label, senior_name, api_url, token) "
                         "VALUES (?, ?, ?, ?, ?)",
                         (device_id, label.strip(), senior_name.strip(), api_url.rstrip("/"),
                          token.strip()))
            conn.commit()
        finally:
            conn.close()

    def remove_device(self, device_id: str) -> bool:
        conn = self._conn()
        try:
            n = conn.execute("DELETE FROM devices WHERE id = ?", (device_id,)).rowcount
            conn.commit()
        finally:
            conn.close()
        return n > 0

    def assign(self, login: str, device_id: str) -> None:
        account = self.account(login)
        if account is None:
            raise DirectoryError("Konto unbekannt")
        if self.device(device_id) is None:
            raise DirectoryError("Gerät unbekannt")
        if account["role"] == "admin":
            raise DirectoryError("Admin sieht alle Geräte (nur Technik), keine Zuordnung nötig")
        if account["role"] == "angehoerige":
            current = [d["id"] for d in self.devices_for(account)]
            if current and current != [device_id]:
                raise DirectoryError("Angehörige sehen genau eine Seniorin/einen Senior (B4)")
        conn = self._conn()
        try:
            conn.execute("INSERT OR IGNORE INTO assignments (login, device_id) VALUES (?, ?)",
                         (login, device_id))
            conn.commit()
        finally:
            conn.close()

    def unassign(self, login: str, device_id: str) -> bool:
        conn = self._conn()
        try:
            n = conn.execute("DELETE FROM assignments WHERE login = ? AND device_id = ?",
                             (login, device_id)).rowcount
            conn.commit()
        finally:
            conn.close()
        return n > 0

    _DEVICE_COLS = ("id", "label", "senior_name", "api_url", "token", "last_seen")

    def device(self, device_id: str) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(f"SELECT {', '.join(self._DEVICE_COLS)} FROM devices WHERE id = ?",
                               (device_id,)).fetchone()
        finally:
            conn.close()
        return dict(zip(self._DEVICE_COLS, row)) if row else None

    def devices_for(self, account: dict) -> list[dict]:
        conn = self._conn()
        try:
            if account["role"] == "admin":
                rows = conn.execute(f"SELECT {', '.join(self._DEVICE_COLS)} FROM devices "
                                    "ORDER BY senior_name").fetchall()
            else:
                rows = conn.execute(
                    f"SELECT {', '.join('d.' + c for c in self._DEVICE_COLS)} FROM devices d "
                    "JOIN assignments a ON a.device_id = d.id WHERE a.login = ? "
                    "ORDER BY d.senior_name", (account["login"],)).fetchall()
        finally:
            conn.close()
        return [dict(zip(self._DEVICE_COLS, r)) for r in rows]

    def mark_seen(self, device_id: str) -> None:
        conn = self._conn()
        try:
            conn.execute("UPDATE devices SET last_seen = ? WHERE id = ?", (_iso(_now()), device_id))
            conn.commit()
        finally:
            conn.close()


# --- passwords (scrypt) ---

_SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, dklen=32, **_SCRYPT)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_b64, digest_b64 = stored.split("$")
        digest = hashlib.scrypt((password or "").encode("utf-8"),
                                salt=base64.b64decode(salt_b64), dklen=32, **_SCRYPT)
        return hmac.compare_digest(digest, base64.b64decode(digest_b64))
    except (ValueError, TypeError):
        return False


_DUMMY_HASH = hash_password("x" * MIN_PASSWORD)


# --- second factor: TOTP, RFC 6238 (30 s, 6 digits, SHA-1 like common apps) ---

def totp(secret: str, at: float, step: int = 30, digits: int = 6) -> str:
    key = base64.b32decode(secret)
    counter = struct.pack(">Q", int(at // step))
    mac = hmac.new(key, counter, hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    value = struct.unpack(">I", mac[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10 ** digits).zfill(digits)


def verify_totp(secret: str, code: str, now: float | None = None) -> bool:
    """Accepts the current code and one step before/after (clock drift)."""
    code = (code or "").strip().replace(" ", "")
    if not re.fullmatch(r"\d{6}", code):
        return False
    now = now or time.time()
    return any(hmac.compare_digest(totp(secret, now + d * 30), code) for d in (-1, 0, 1))


def otpauth_uri(secret: str, login: str) -> str:
    from urllib.parse import quote
    return (f"otpauth://totp/SeniorVoice:{quote(login)}?secret={secret}"
            "&issuer=SeniorVoice&algorithm=SHA1&digits=6&period=30")
