"""Bringt eine .env aus einer früheren Einrichtung auf den aktuellen Stand.

Läuft bei jedem Start (scripts/vorbereiten.sh), damit niemand nach einem
Update von Hand nachjustieren muss. Ändert nur Werte, die heute den Start
verderben würden, und legt vorher eine Kopie an (.env.vorher-<Zeit>).

Heute eine Regel:
- SIM_AUDIO=text oder SIM_AUDIO=audio aus der ersten Einrichtung wird
  auskommentiert. Seit dem automatischen Ton gehen Sprechen und Tippen immer
  beide; nur Tippen gibt es für einen einzelnen Start mit
  `SIM_AUDIO=text scripts/start-demo.sh`.

Aufruf: python scripts/upgrade_env.py [Pfad zur .env]
"""

import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_SIM_AUDIO = re.compile(r"""^[ \t]*(?:export[ \t]+)?SIM_AUDIO[ \t]*=[ \t]*["']?(text|audio)["']?[ \t]*$""",
                        re.M | re.I)


def upgrade_text(text: str) -> tuple[str, list[str]]:
    """Return the upgraded .env text and one message per change."""
    messages = []

    def _off(m: re.Match) -> str:
        value = m.group(1).lower()
        messages.append(f"SIM_AUDIO={value} aus der ersten Einrichtung ausgeschaltet: "
                        "Sprechen und Tippen gehen jetzt immer beide.")
        return (f"# SIM_AUDIO={value}\n"
                "# (beim Start ausgeschaltet: der Ton wird automatisch gewählt. "
                "Nur Tippen für einen Start: SIM_AUDIO=text scripts/start-demo.sh)")

    return _SIM_AUDIO.sub(_off, text), messages


def upgrade(path: Path, now: datetime | None = None) -> list[str]:
    """Upgrade the file in place (with a backup). Returns what changed."""
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    new, messages = upgrade_text(text)
    if new == text:
        return []
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.name}.vorher-{stamp}")
    shutil.copy2(path, backup)
    os.chmod(backup, 0o600)
    path.write_text(new, encoding="utf-8")
    messages.append(f"Kopie der alten Datei: {backup.name}")
    return messages


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / ".env"
    for line in upgrade(path):
        print(f"  .env: {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
