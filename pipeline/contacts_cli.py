#!/usr/bin/env python3
"""Help contacts, in order (A15), until the portal exists (PR 10).

Default order: relatives first, then Spitex. Set only with the senior's consent.

    python contacts_cli.py set "Sandra|Tochter|123456789" "Spitex Winterthur|Spitex|987654321"
    python contacts_cli.py list

The address is the contact's Telegram chat id (CHANNEL=telegram) or any
label for the console channel.
"""

import sys

from logging_config import setup_logging
import help_alert


def main() -> None:
    setup_logging()
    if len(sys.argv) >= 2 and sys.argv[1] == "list":
        for c in help_alert.get_contacts():
            print(f"{c['position'] + 1}. {c['name']} ({c['role']}) -> {c['address']}")
        return
    if len(sys.argv) >= 3 and sys.argv[1] == "set":
        contacts = []
        for item in sys.argv[2:]:
            name, role, address = (part.strip() for part in item.split("|"))
            contacts.append({"name": name, "role": role, "address": address})
        help_alert.set_contacts(contacts)
        print(f"{len(contacts)} Kontaktperson(en) gespeichert")
        return
    print(__doc__)


if __name__ == "__main__":
    main()
