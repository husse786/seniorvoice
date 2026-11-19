#!/usr/bin/env bash
# Vor jedem Start (start-demo.sh, start-simulation.sh): macht den Rechner
# startklar, ohne dass jemand nachjustieren muss.
#   - Erste Einrichtung (keine .env oder kein Gerätetoken): legt die
#     Demo-Personen an (scripts/demo-personen.sh, fragt einmal Passwörter).
#     Danach prüft es bei jedem Start still, ob alles noch da ist (z. B. nach
#     dem Löschen der Testdaten), und legt nur Fehlendes neu an.
#   - Ältere .env: bringt sie auf den aktuellen Stand (scripts/upgrade_env.py).
#   - Fehlt etwas für den Ton (Whisper, Piper, deutsche Stimme), wird es in
#     die virtuelle Umgebung .venv nachinstalliert. Ohne Internet läuft der
#     Start trotzdem, dann nur mit Tippen, und die Telefon-Seite sagt warum.
# Darf beliebig oft laufen; ohne Bedarf ändert es nichts und sagt nichts.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${PYTHON:-$ROOT/.venv/bin/python}"
[ -x "$PY" ] || PY="$(command -v python3)"

if [ -f .env ]; then
  "$PY" scripts/upgrade_env.py .env || echo "  .env konnte nicht geprüft werden, Start läuft weiter."
fi
if [ -x "$ROOT/.venv/bin/python" ] && [ "$(uname -s)" = Darwin ] && [ "${SIM_AUDIO:-}" != text ]; then
  VENV="$ROOT/.venv/bin"
  if ! "$VENV/python" -c "import faster_whisper, sounddevice" 2>/dev/null || [ ! -x "$VENV/piper" ]; then
    echo "Ton: Whisper oder Piper fehlt, wird einmal nachinstalliert …"
    "$VENV/python" -m pip install -q -r pipeline/requirements.txt piper-tts \
      || echo "  Nachinstallieren ging nicht (Internet?). Start nur mit Tippen."
  fi
  VOICE_DIR="$HOME/.local/share/piper-voices"
  if [ -z "${PIPER_VOICE:-}" ] && [ ! -f "$VOICE_DIR/de_DE-thorsten-medium.onnx" ] && [ -x "$VENV/piper" ]; then
    echo "Ton: deutsche Stimme fehlt, wird einmal geladen …"
    "$VENV/python" -m piper.download_voices --data-dir "$VOICE_DIR" de_DE-thorsten-medium \
      || echo "  Laden ging nicht (Internet?). Start nur mit Tippen."
  fi
fi
TOKEN_HASH=""
if [ -f .env ]; then
  TOKEN_HASH="$(sed -n 's/^[[:space:]]*DEVICE_API_TOKEN_SHA256=["'\'']\{0,1\}\([0-9a-fA-F]*\).*/\1/p' .env | tail -n1)"
fi
if [ -z "$TOKEN_HASH" ]; then
  echo "Erste Einrichtung: Demo-Personen und Gerätetoken werden angelegt."
  "$ROOT/scripts/demo-personen.sh"
  echo
else
  # Gelöschte Testdaten (Portal oder Gerät) still wieder anlegen, ohne Beispieltermine
  "$ROOT/scripts/demo-personen.sh" --still --ohne-termine \
    || echo "  Prüfung der Demo-Personen ging nicht (scripts/demo-personen.sh von Hand starten). Start läuft weiter."
fi
