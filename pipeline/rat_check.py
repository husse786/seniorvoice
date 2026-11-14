#!/usr/bin/env python3
"""Check the Rat button with the fixed test questions (test A-3, B2).

Runs on the device with the real local model. Uses a temporary database
with invented entries, so the senior's data is neither read nor changed.
Prints one line per question and exits with 1 if any answer is wrong.

What is checked: whether the right entry (or none) is chosen. That the
device never says anything of its own holds by construction: it speaks
either a fixed sentence or an entered text (see advice.py, and the unit
tests in tests/test_advice.py).

    python rat_check.py
"""

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="rat-check-")
    os.environ["MEMORY_DB_PATH"] = os.path.join(tmp, "rat-check.db")
    import advice            # after MEMORY_DB_PATH: config reads it on import
    from logging_config import setup_logging
    setup_logging()

    data = json.loads((HERE / "rat_testfragen.json").read_text(encoding="utf-8"))
    ids = [advice.add_item(e["topic"], e["text"], e["by"]) for e in data["eintraege"]]
    number = {item_id: n for n, item_id in enumerate(ids, start=1)}
    items = advice.list_items()

    failed = 0
    for q in data["fragen"]:
        item = advice.find_item(q["frage"], items)
        got = number[item["id"]] if item else 0
        ok = got == q["erwartet"] or got in q.get("erlaubt", [])
        failed += not ok
        print(f"{'OK   ' if ok else 'FEHLER'}  {q['gruppe']:16}  erwartet {q['erwartet']}, gewählt {got}  {q['frage']}")
    total = len(data["fragen"])
    print(f"\n{total - failed} von {total} richtig")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
