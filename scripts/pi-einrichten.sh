#!/usr/bin/env bash
# Richtet einen Raspberry Pi 5 (Raspberry Pi OS Lite, 64 bit) als SeniorVoice-
# Gerät ein. Darf beliebig oft laufen: Vorhandenes bleibt, Fehlendes kommt dazu.
# Aufruf auf dem Pi, im Ordner seniorvoice:   scripts/pi-einrichten.sh
#   --trocken   nur anzeigen, was es tun würde
#
# Was es macht:
#   1. Programme (apt): Python, Ton, GPIO, WireGuard, Bildschirm ohne Desktop
#   2. virtuelle Umgebung .venv mit allen Python-Paketen
#   3. Sprachmodell (Ollama) und deutsche Stimme (Piper)
#   4. .env aus .env.example, erkannte Hardware eintragen (hardware_erkennen.py)
#   5. Dienste: Telefon, Geräte-API, Bildschirm; Benutzer und Pfade passend
#   6. Selbsttest (check-device.sh)
# Was es nicht macht: Gerätetoken, Freigaben und Hilfe-Kontakte (Zustimmung der
# Seniorin oder des Seniors, docs/pi-einrichten.md Schritt 1) und den
# WireGuard-Tunnel (docs/wireguard.md).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
DRY=0; [ "${1:-}" = "--trocken" ] && DRY=1
run() { if [ "$DRY" = 1 ]; then echo "  würde: $*"; else "$@"; fi; }
say() { echo; echo "== $*"; }
USER_NAME="$(id -un)"
MODEL="${LLM_MODEL:-gemma3:1b}"

if [ "$(uname -s)" != Linux ] || ! grep -qi "raspberry pi" /proc/device-tree/model 2>/dev/null; then
  echo "Kein Raspberry Pi erkannt. Auf dem Mac: scripts/start-demo.sh (docs/simulation.md)."
  [ "$DRY" = 1 ] || exit 1
fi

say "1/6 Programme"
CHROMIUM=chromium
apt-cache show chromium >/dev/null 2>&1 || CHROMIUM=chromium-browser
run sudo apt-get update -q
run sudo apt-get install -y -q git curl python3-venv python3-lgpio alsa-utils libportaudio2 \
  gpiod wireguard-tools cage "$CHROMIUM" wlr-randr

say "2/6 Python-Umgebung"
[ -d .venv ] || run python3 -m venv --system-site-packages .venv
run .venv/bin/pip install -q -r pipeline/requirements.txt piper-tts

say "3/6 Sprachmodell und Stimme"
command -v ollama >/dev/null || run sh -c "curl -fsSL https://ollama.com/install.sh | sh"
if [ "$DRY" = 1 ] || ! ollama list 2>/dev/null | grep -q "^${MODEL}"; then run ollama pull "$MODEL"; fi
VOICES="$HOME/.local/share/piper-voices"
[ -f "$VOICES/de_DE-thorsten-medium.onnx" ] || run .venv/bin/python -m piper.download_voices --data-dir "$VOICES" de_DE-thorsten-medium

say "4/6 Einstellungen"
if [ ! -f .env ]; then run cp .env.example .env; run chmod 600 .env; fi
run .venv/bin/python scripts/upgrade_env.py .env
run .venv/bin/python scripts/hardware_erkennen.py --schreiben || true

say "5/6 Dienste (Benutzer $USER_NAME, Ordner $ROOT)"
for unit in seniorvoice seniorvoice-api seniorvoice-screen; do
  TMP="$(mktemp)"
  sed -e "s#/home/pi/seniorvoice#$ROOT#g" -e "s#^User=pi\$#User=$USER_NAME#" "deploy/$unit.service" > "$TMP"
  run sudo install -m 644 "$TMP" "/etc/systemd/system/$unit.service"
  rm -f "$TMP"
done
run sudo systemctl daemon-reload
run sudo systemctl enable seniorvoice
run sudo systemctl restart seniorvoice
if grep -qE '^[[:space:]]*DEVICE_API_TOKEN_SHA256=[0-9a-f]{64}' .env 2>/dev/null; then
  run sudo systemctl enable seniorvoice-api; run sudo systemctl restart seniorvoice-api
else
  echo "  Geräte-API wartet auf den Gerätetoken (docs/pi-einrichten.md, Schritt 1)."
fi
if grep -q connected /sys/class/drm/card*-DSI-*/status /sys/class/drm/card*-HDMI-*/status 2>/dev/null \
   && ! grep -qiE '^[[:space:]]*SCREEN_ENABLED=(false|0|no)' .env 2>/dev/null; then
  run sudo systemctl enable seniorvoice-screen; run sudo systemctl restart seniorvoice-screen
else
  echo "  Kein Bildschirm angeschlossen: Bildschirm-Dienst bleibt aus (später dieses Skript nochmals laufen lassen)."
fi

say "6/6 Selbsttest"
if [ "$DRY" = 1 ]; then echo "  würde: scripts/check-device.sh"; else sleep 3; scripts/check-device.sh || true; fi
