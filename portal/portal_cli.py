#!/usr/bin/env python3
"""Manage the portal directory (D16): accounts, devices, assignments.

The directory is the only store of the portal (B4). It holds the device
tokens, so the file is created readable by its owner only.

    python portal_cli.py add-account sandra.keller "Sandra Keller" angehoerige
    python portal_cli.py add-device keller "Telefon Frau Keller" "Frau Keller" \\
        http://127.0.0.1:8770
    python portal_cli.py assign sandra.keller keller
    python portal_cli.py list

The login must be the same id as the grant on the device
(device_api_cli.py grant <login> ...), otherwise the device answers 403.
"""

import argparse
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from directory import Directory, DirectoryError, otpauth_uri  # noqa: E402

PORTAL_DB = os.getenv("PORTAL_DB", str(Path.home() / "seniorvoice-portal" / "portal.db"))


def _ask_secret(prompt: str, env: str) -> str:
    value = os.getenv(env)
    if value:
        return value
    return getpass.getpass(prompt)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="SeniorVoice portal directory")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add-account", help="new account; prints the authenticator link")
    a.add_argument("login")
    a.add_argument("name")
    a.add_argument("role", choices=("angehoerige", "spitex", "admin"))
    r = sub.add_parser("remove-account")
    r.add_argument("login")
    d = sub.add_parser("add-device", help="device token is asked (or PORTAL_DEVICE_TOKEN)")
    d.add_argument("device_id")
    d.add_argument("label")
    d.add_argument("senior_name")
    d.add_argument("api_url", help="e.g. http://10.77.0.2:8770 (tunnel) or http://127.0.0.1:8770")
    rd = sub.add_parser("remove-device")
    rd.add_argument("device_id")
    s = sub.add_parser("assign")
    s.add_argument("login")
    s.add_argument("device_id")
    u = sub.add_parser("unassign")
    u.add_argument("login")
    u.add_argument("device_id")
    sub.add_parser("list")
    args = p.parse_args(argv)

    directory = Directory(PORTAL_DB)
    try:
        if args.cmd == "add-account":
            password = _ask_secret("Passwort (mind. 10 Zeichen): ", "PORTAL_PASSWORD")
            secret = directory.add_account(args.login, args.name, args.role, password)
            print("Konto angelegt. In der Authenticator-App (z.B. als QR-Code) eintragen:")
            print(otpauth_uri(secret, args.login))
            print(f"oder manuell den Schlüssel: {secret}")
        elif args.cmd == "remove-account":
            print("entfernt" if directory.remove_account(args.login) else "unbekannt")
        elif args.cmd == "add-device":
            token = _ask_secret("Gerätetoken (device_api_cli.py token): ", "PORTAL_DEVICE_TOKEN")
            directory.add_device(args.device_id, args.label, args.senior_name, args.api_url, token)
            print("Gerät eingetragen.")
        elif args.cmd == "remove-device":
            print("entfernt" if directory.remove_device(args.device_id) else "unbekannt")
        elif args.cmd == "assign":
            directory.assign(args.login, args.device_id)
            print("zugeordnet")
        elif args.cmd == "unassign":
            print("aufgehoben" if directory.unassign(args.login, args.device_id) else "unbekannt")
        elif args.cmd == "list":
            print("Konten:")
            for acc in directory.accounts():
                devices = ", ".join(x["id"] for x in directory.devices_for(acc))
                print(f"  {acc['login']:24} {acc['role']:12} {acc['name']}  [{devices}]")
            print("Geräte:")
            for dev in directory.devices_for({"role": "admin", "login": ""}):
                print(f"  {dev['id']:16} {dev['api_url']:28} {dev['senior_name']} "
                      f"(zuletzt erreicht: {dev['last_seen'] or 'nie'})")
    except DirectoryError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
