"""Legt die Demo-Personen an, damit ein frischer Laptop in einer Minute
demo-bereit ist. Aufruf über scripts/demo-personen.sh (lädt .env).

Darf beliebig oft laufen: was schon da ist, bleibt unverändert. Insbesondere
werden bestehende Portal-Konten nie überschrieben.

- Gerät «Frau Keller»: SENIOR_NAME in .env, Gerätetoken (Hash in .env, Token
  im Portal, beide passend)
- Freigaben am Gerät mit Einwilligung (B4): sandra.keller (Angehörige,
  Hilfe sichtbar) und admin.team (Admin)
- Hilfe-Kontakt Sandra (T3: bei der Einrichtung, mit Zustimmung)
- Portal-Konten sandra.keller und admin.team (Passwort wird gefragt,
  TOTP-Schlüssel einmal angezeigt), Gerät im Portal, Zuordnung
- Beispieltermine, nur wenn keine künftigen Termine da sind

Keine Zugangsdaten landen im Repository: das Passwort wird nur abgefragt,
der Token nur in .env (Hash) und in der Portal-Datenbank gespeichert.
"""

import getpass
import os
import re
import secrets
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "portal"))

DEVICE_ID = "keller"
SENIOR = "Frau Keller"
PEOPLE = [
    # login, name, role, help visible, assigned to the device in the portal
    ("sandra.keller", "Sandra Keller", "angehoerige", True),
    ("admin.team", "Projektteam", "admin", False),
]


def say(text: str) -> None:
    print(f"  {text}")


def env_file() -> Path:
    path = ROOT / ".env"
    if not path.exists():
        path.write_text((ROOT / ".env.example").read_text(encoding="utf-8"), encoding="utf-8")
        os.chmod(path, 0o600)
        say(".env aus .env.example angelegt")
    return path


def set_env_line(path: Path, key: str, value: str) -> None:
    """Set KEY=value in .env (replaces a commented or empty line)."""
    text = path.read_text(encoding="utf-8")
    line = f"{key}={value}"
    pattern = re.compile(rf"^#?\s*{re.escape(key)}=.*$", re.M)
    text = pattern.sub(line, text, count=1) if pattern.search(text) else text.rstrip("\n") + f"\n{line}\n"
    path.write_text(text, encoding="utf-8")
    os.environ[key] = value


def ask_password(login: str) -> str:
    env = os.getenv("PORTAL_PASSWORD")
    if env:
        return env
    while True:
        first = getpass.getpass(f"  Passwort für {login} (mind. 10 Zeichen): ")
        if len(first) < 10:
            print("  Zu kurz.")
            continue
        if getpass.getpass("  Nochmals: ") == first:
            return first
        print("  Stimmt nicht überein.")


def main() -> int:
    env_path = env_file()
    if not os.getenv("SENIOR_NAME"):
        set_env_line(env_path, "SENIOR_NAME", f'"{SENIOR}"')
        os.environ["SENIOR_NAME"] = SENIOR
        say(f"SENIOR_NAME={SENIOR} in .env")

    import device_api
    from directory import Directory, DirectoryError, otpauth_uri
    portal_db = os.getenv("PORTAL_DB", str(Path.home() / "seniorvoice-portal" / "portal.db"))

    print("Gerät")
    directory = Directory(portal_db)
    api_url = f"http://127.0.0.1:{os.getenv('DEVICE_API_PORT', '8770')}"
    current_hash = os.getenv("DEVICE_API_TOKEN_SHA256", "").strip()
    device = directory.device(DEVICE_ID)
    if device and current_hash and device_api.token_hash(device["token"]) == current_hash:
        say("Gerätetoken passt zum Portal (unverändert)")
    else:
        token = secrets.token_urlsafe(32)
        set_env_line(env_path, "DEVICE_API_TOKEN_SHA256", device_api.token_hash(token))
        directory.add_device(DEVICE_ID, "Telefon Frau Keller", SENIOR, api_url, token)
        say("Neuer Gerätetoken: Hash in .env, Token im Portal")
        say("Läuft die Simulation schon, bitte neu starten.")

    granted = {g["person_id"] for g in device_api.list_grants()}
    for login, name, role, help_visible in PEOPLE:
        if login in granted:
            say(f"Freigabe {login}: schon da")
        else:
            device_api.grant(login, name, role, help_visible=help_visible)
            say(f"Freigabe {login} ({role}) mit Einwilligung gespeichert")

    import help_alert
    if help_alert.get_contacts():
        say("Hilfe-Kontakte: schon da (unverändert)")
    else:
        address = "Sandra"
        if os.getenv("CHANNEL", "console") == "email":
            address = input("  E-Mail-Adresse von Sandra (Hilfe-Kontakt): ").strip() or "Sandra"
        help_alert.set_contacts([{"name": "Sandra Keller", "role": "Tochter", "address": address}])
        say("Hilfe-Kontakt Sandra Keller (Tochter) eingetragen")

    import appointments
    now = datetime.now(appointments.LOCAL_TZ).replace(tzinfo=None)
    now_utc = appointments._iso(appointments._now_utc())
    future = [a for a in appointments.list_appointments() if a["due_at"] >= now_utc]
    if future:
        say("Termine: schon da (unverändert)")
    else:
        tomorrow = (now + timedelta(days=1)).replace(second=0, microsecond=0)
        appointments.add_appointment("Hausarzt Dr. Meier", tomorrow.replace(hour=10, minute=0), "Demo")
        appointments.add_appointment("Blutdruck-Tablette", tomorrow.replace(hour=8, minute=0), "Demo",
                                     kind="medikament")
        say("Beispieltermine für morgen eingetragen (08:00 Tablette, 10:00 Hausarzt)")

    print("Portal")
    logins = {a["login"] for a in directory.accounts()}
    for login, name, role, _ in PEOPLE:
        if login in logins:
            say(f"Konto {login}: schon da (Passwort und Code unverändert)")
        else:
            secret = directory.add_account(login, name, role, ask_password(login))
            say(f"Konto {login} angelegt. Bitte jetzt sichern (z. B. in der Passwörter-App des Mac):")
            say(f"  Code-Schlüssel (TOTP): {secret}")
            say(f"  Link für die Authenticator-App: {otpauth_uri(secret, login)}")
        if role != "admin":
            try:
                directory.assign(login, DEVICE_ID)   # no-op if already assigned
            except DirectoryError as e:
                say(f"Zuordnung {login}: {e}")
    print()
    print("Fertig. Starten: scripts/start-simulation.sh und scripts/start-portal.sh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
