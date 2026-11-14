#!/usr/bin/env python3
"""Enter information for the Rat button at the device (B2).

The device reads the text verbatim when a question fits the topic. Spitex
or relatives enter it; the same is possible over the portal (device API).

Examples:
    python advice_cli.py add "Telefonnummer Spitex" "Die Spitex erreichen Sie unter 044 000 00 00." --by Spitex
    python advice_cli.py add "Weisse Tablette" "Die weisse Tablette nach dem Frühstück mit Wasser nehmen." --by Spitex
    python advice_cli.py list
    python advice_cli.py delete 2
"""

import argparse
import sys

from logging_config import setup_logging
import advice


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    add = sub.add_parser("add")
    add.add_argument("topic", help=f"short topic, at most {advice.MAX_TOPIC} characters")
    add.add_argument("text", help=f"read out verbatim, at most {advice.MAX_TEXT} characters")
    add.add_argument("--by", required=True, help="who entered it (B5), is read out")
    sub.add_parser("list")
    delete = sub.add_parser("delete")
    delete.add_argument("id", type=int)
    args = parser.parse_args()

    setup_logging()
    try:
        if args.cmd == "add":
            print(f"Gespeichert (Nr. {advice.add_item(args.topic, args.text, args.by)})")
        elif args.cmd == "delete":
            print("Gelöscht" if advice.delete_item(args.id) else "Nicht gefunden")
        else:
            for item in advice.list_items():
                print(f"{item['id']:3}  {item['topic']}  ({item['created_by']})\n     {item['text']}")
    except advice.AdviceError as e:
        sys.exit(f"Fehler: {e}")


if __name__ == "__main__":
    main()
