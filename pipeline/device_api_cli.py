#!/usr/bin/env python3
"""Set up the device API for the portal (PR 10), on the device itself.

Grants are stored on the device, only with the senior's consent (B4). The
portal cannot grant itself access.

    python device_api_cli.py token
        New device token: give the token to the portal, put the hash in .env
    python device_api_cli.py grant sandra.keller "Sandra Keller" angehoerige --help-visible --senior-consent
    python device_api_cli.py grant spitex.mueller "M. Müller (Spitex)" spitex --senior-consent
    python device_api_cli.py grant admin.team "Projektteam" admin --senior-consent
    python device_api_cli.py revoke sandra.keller
    python device_api_cli.py list
    python device_api_cli.py audit [--person sandra.keller]
"""

import argparse
import secrets

import device_api
from logging_config import setup_logging


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("token")
    g = sub.add_parser("grant")
    g.add_argument("person_id", help="portal account id")
    g.add_argument("name", help="shown as 'entered by'")
    g.add_argument("role", choices=device_api.ROLES)
    g.add_argument("--help-visible", action="store_true",
                   help="may see the Help history (Help contacts)")
    g.add_argument("--senior-consent", action="store_true",
                   help="required: the senior has agreed to this access")
    r = sub.add_parser("revoke")
    r.add_argument("person_id")
    sub.add_parser("list")
    a = sub.add_parser("audit")
    a.add_argument("--person", default=None)
    args = parser.parse_args()

    setup_logging()
    if args.cmd == "token":
        token = secrets.token_urlsafe(32)
        print("Token für das Portal (nur einmal angezeigt, sicher übergeben):")
        print(f"  {token}")
        print("Zeile für .env auf diesem Gerät:")
        print(f"  DEVICE_API_TOKEN_SHA256={device_api.token_hash(token)}")
    elif args.cmd == "grant":
        if not args.senior_consent:
            parser.error("--senior-consent fehlt: Zugriff nur mit Zustimmung der Seniorin/des Seniors")
        device_api.grant(args.person_id, args.name, args.role, args.help_visible)
        print(f"Freigabe gespeichert: {args.person_id} ({args.role})")
    elif args.cmd == "revoke":
        print("Freigabe entfernt" if device_api.revoke(args.person_id) else "Keine solche Freigabe")
    elif args.cmd == "list":
        for g in device_api.list_grants():
            help_flag = ", Help-Verlauf" if g["help_visible"] else ""
            print(f"{g['person_id']}: {g['name']} ({g['role']}{help_flag}), seit {g['granted_at']}")
    else:
        for e in device_api.list_audit(args.person):
            print(f"{e['at']}  {e['person_id']:20}  {e['action']:32}  {e['target'] or '':6}  {e['result']}")


if __name__ == "__main__":
    main()
