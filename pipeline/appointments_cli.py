#!/usr/bin/env python3
"""Enter and list appointments until the portal exists (PR 10).

Examples:
    python appointments_cli.py add "Arzttermin bei Dr. Meier" "2026-11-20 14:00" --by Spitex
    python appointments_cli.py add "1 Tablette Marcoumar" "2026-11-20 08:00" --kind medikament --by Tochter
    python appointments_cli.py list
"""

import argparse
from datetime import datetime

from logging_config import setup_logging
import appointments


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    add = sub.add_parser("add")
    add.add_argument("title", help="read out verbatim")
    add.add_argument("when", help='local time, "YYYY-MM-DD HH:MM"')
    add.add_argument("--by", required=True, help="who entered it (B5)")
    add.add_argument("--kind", choices=appointments.KINDS, default="termin")
    add.add_argument("--pre", type=int, default=None, help="pre-reminder minutes")
    sub.add_parser("list")
    args = parser.parse_args()

    setup_logging()
    if args.cmd == "add":
        due = datetime.strptime(args.when, "%Y-%m-%d %H:%M")
        appt_id = appointments.add_appointment(args.title, due, args.by, args.kind, args.pre)
        print(f"Gespeichert (Nr. {appt_id})")
    else:
        for r in appointments.list_reminders():
            print(f"{r['due_at']}  {r['stage']:4}  {r['status']:10}  {r['kind']:10}  {r['title']}  ({r['created_by']})")


if __name__ == "__main__":
    main()
