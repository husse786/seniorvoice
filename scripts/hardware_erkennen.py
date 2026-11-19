"""Erkennt am Pi, was angeschlossen ist, und schlägt die passenden Werte für
.env vor. Liest nur Systemdateien und `gpiodetect`; ändert nichts, ausser mit
--schreiben: dann trägt es fehlende oder auskommentierte Zeilen in .env ein
und aktualisiert Werte, die es selbst früher eingetragen hat (Zeile darüber
«# erkannt»). Einen Wert, den jemand selbst gesetzt hat, ändert es nie.

    python scripts/hardware_erkennen.py             # Bericht
    python scripts/hardware_erkennen.py --schreiben # fehlende Werte in .env

Erkannt wird:
- GPIO-Chip des Pi 5 (pinctrl-rp1)       -> GPIO_CHIP
- Tonkarten «handset» und «speaker» (udev-Regel, inbetriebnahme-telefon.md 4.3),
  sonst eine einzelne USB-Tonkarte für beides (Zwischenaufbau)
                                         -> HANDSET_ALSA_DEVICE, SPEAKER_ALSA_DEVICE
- Webcam-Mikrofon C920                   -> AUDIO_DEVICE_NAME
- Bildschirm am DSI-Anschluss (Touch Display 2) oder HDMI (nur Bericht)

Gabel und Knöpfe lassen sich nicht erkennen, ohne dass jemand drückt:
dafür inbetriebnahme-telefon.md 4.2.
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def gpio_chip(gpiodetect_output: str) -> str | None:
    """'gpiochip0 [pinctrl-rp1] (54 lines)' -> '0'."""
    for line in gpiodetect_output.splitlines():
        m = re.match(r"\s*gpiochip(\d+)\s+\[pinctrl-rp1\]", line)
        if m:
            return m.group(1)
    return None


def sound_cards(proc_cards: str) -> list[dict]:
    """/proc/asound/cards -> [{'nr': '2', 'id': 'handset', 'driver': 'USB-Audio', 'name': '...'}]."""
    cards = []
    for line in proc_cards.splitlines():
        m = re.match(r"\s*(\d+)\s+\[(\S+)\s*\]:\s+(\S+)\s+-\s+(.*)$", line)
        if m:
            cards.append({"nr": m.group(1), "id": m.group(2), "driver": m.group(3),
                          "name": m.group(4).strip()})
    return cards


def displays(drm: Path) -> dict[str, bool]:
    """{'DSI-1': True, 'HDMI-A-1': False} from /sys/class/drm/card*-*/status."""
    found = {}
    for status in sorted(drm.glob("card*-*/status")):
        name = status.parent.name.split("-", 1)[1]
        try:
            found[name] = status.read_text().strip() == "connected"
        except OSError:
            continue
    return found


def detect(proc_cards: str, gpiodetect_output: str, drm: Path) -> tuple[dict, list[tuple[str, str]]]:
    """Return (suggested .env values, report lines (level, text))."""
    values: dict[str, str] = {}
    report: list[tuple[str, str]] = []

    chip = gpio_chip(gpiodetect_output)
    if chip is not None:
        values["GPIO_CHIP"] = chip
        report.append(("OK", f"GPIO-Chip des Pi 5: gpiochip{chip} (GPIO_CHIP={chip})"))
    else:
        report.append(("WARNUNG", "GPIO-Chip pinctrl-rp1 nicht gefunden (gpiodetect installiert? sudo apt install gpiod)"))

    cards = sound_cards(proc_cards)
    ids = {c["id"].lower(): c for c in cards}
    usb = [c for c in cards if c["driver"] == "USB-Audio"]
    if "handset" in ids and "speaker" in ids:
        values["HANDSET_ALSA_DEVICE"] = "plughw:CARD=handset,DEV=0"
        values["SPEAKER_ALSA_DEVICE"] = "plughw:CARD=speaker,DEV=0"
        report.append(("OK", "Tonkarten «handset» (Hörer) und «speaker» (Raum) benannt"))
    else:
        out = [c for c in usb if c["id"].lower() not in ("c920",)]
        if "handset" in ids or "speaker" in ids:
            have = "handset" if "handset" in ids else "speaker"
            report.append(("WARNUNG", f"nur die Tonkarte «{have}» ist benannt, die zweite fehlt "
                                      "(inbetriebnahme-telefon.md 4.3)"))
        if len(out) == 1:
            dev = f"plughw:CARD={out[0]['id']},DEV=0"
            values["HANDSET_ALSA_DEVICE"] = dev
            values["SPEAKER_ALSA_DEVICE"] = dev
            report.append(("WARNUNG", f"eine USB-Tonkarte «{out[0]['id']}» für Hörer und Raum "
                                      "(Zwischenaufbau, bis zwei Adapter da sind)"))
        elif not out:
            report.append(("FEHLT", "keine USB-Tonkarte für den Ton (der Pi 5 hat keine Kopfhörerbuchse)"))
        else:
            names = ", ".join(c["id"] for c in out)
            report.append(("WARNUNG", f"mehrere USB-Tonkarten ({names}): mit udev-Regel «handset» und "
                                      "«speaker» benennen (inbetriebnahme-telefon.md 4.3)"))

    if "c920" in ids:
        values["AUDIO_DEVICE_NAME"] = "C920"
        report.append(("OK", "Mikrofon: Webcam C920"))
    elif "handset" in ids:
        report.append(("WARNUNG", "Hörer-Mikrofon: AUDIO_DEVICE_NAME von Hand setzen, Teil des Namens "
                                  f"«{ids['handset']['name']}» (inbetriebnahme-telefon.md 4.4)"))
    else:
        report.append(("WARNUNG", "kein bekanntes Mikrofon (C920 oder Tonkarte «handset»)"))

    shown = displays(drm)
    dsi = [n for n, on in shown.items() if on and n.startswith("DSI")]
    hdmi = [n for n, on in shown.items() if on and n.startswith("HDMI")]
    if dsi or hdmi:
        report.append(("OK", f"Bildschirm: {', '.join(dsi + hdmi)}"))
    else:
        report.append(("WARNUNG", "kein Bildschirm angeschlossen (Touch Display 2 am DSI-Anschluss); "
                                  "das Gerät läuft auch ohne"))
    return values, report


MARK = "# erkannt (scripts/hardware_erkennen.py)"


def _set_missing(env_path: Path, values: dict) -> list[str]:
    """Write keys that are absent or commented out, and update keys this script
    wrote before (marked line above). Never change a value somebody set."""
    text = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    notes = []
    for key, value in values.items():
        line = f"{key}={value}"
        ours = re.compile(rf"^{re.escape(MARK)}\n\s*{re.escape(key)}\s*=(.*)$", re.M)
        active = re.search(rf"^\s*{re.escape(key)}\s*=(.*)$", text, re.M)
        if active:
            current = active.group(1).strip().strip('"\'')
            if current == value:
                continue
            if ours.search(text):
                text = ours.sub(f"{MARK}\n{line}", text, count=1)
                notes.append(f"{line} aktualisiert (vorher {current})")
            else:
                notes.append(f"{key}={current} bleibt, von Hand gesetzt (erkannt wäre {value})")
            continue
        commented = re.compile(rf"^#\s*{re.escape(key)}\s*=.*$", re.M)
        if commented.search(text):
            text = commented.sub(f"{MARK}\n{line}", text, count=1)
        else:
            text = text.rstrip("\n") + f"\n{MARK}\n{line}\n"
        notes.append(f"{line} eingetragen")
    env_path.write_text(text, encoding="utf-8")
    return notes


def _read(path: str) -> str:
    try:
        return Path(path).read_text()
    except OSError:
        return ""


def _gpiodetect() -> str:
    try:
        return subprocess.run(["gpiodetect"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def main(argv: list[str]) -> int:
    values, report = detect(_read("/proc/asound/cards"), _gpiodetect(), Path("/sys/class/drm"))
    for level, text in report:
        print(f"  {level:<8} {text}")
    if "--schreiben" in argv:
        for note in _set_missing(ROOT / ".env", values):
            print(f"  .env: {note}")
    return 1 if any(level == "FEHLT" for level, _ in report) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
