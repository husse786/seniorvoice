#!/usr/bin/env bash
# Zeigt die Bildschirm-Seite des Geräts (http://127.0.0.1:8772) im Vollbild.
# Läuft unter cage (Kiosk-Fenstermanager ohne Desktop), gestartet vom Dienst
# deploy/seniorvoice-screen.service. Raspberry Pi OS Lite reicht.
#   SCREEN_ROTATE   Drehung des Touch Display 2 in Grad (0, 90, 180, 270).
#                   Das Display ist von Haus aus hochkant; 90 = quer.
#   SCREEN_PORT     Port der Bildschirm-Seite (Standard 8772)
set -uo pipefail
ROTATE="${SCREEN_ROTATE:-90}"
URL="http://127.0.0.1:${SCREEN_PORT:-8772}/"

# Bildschirm drehen (wlroots, unter cage). Ohne wlr-randr bleibt er hochkant.
if command -v wlr-randr >/dev/null; then
  OUTPUT="$(wlr-randr 2>/dev/null | awk '/^DSI-/{print $1; exit}')"
  [ -z "$OUTPUT" ] && OUTPUT="$(wlr-randr 2>/dev/null | awk '/^[A-Z]/{print $1; exit}')"
  case "$ROTATE" in 0) T=normal;; 90|180|270) T="$ROTATE";; *) T=90;; esac
  [ -n "$OUTPUT" ] && wlr-randr --output "$OUTPUT" --transform "$T" || true
fi

# Warten, bis das Gerät die Seite ausliefert (höchstens 2 Minuten)
for _ in $(seq 1 120); do
  curl -s --noproxy '*' -m 1 -o /dev/null "$URL" && break
  sleep 1
done

BROWSER="$(command -v chromium || command -v chromium-browser)"
if [ -z "$BROWSER" ]; then
  echo "Chromium fehlt: sudo apt install chromium" >&2
  exit 1
fi
# Privat: kein Verlauf, kein Cache auf der Karte (A8: Gespräch nur im RAM)
exec "$BROWSER" --kiosk --incognito --noerrdialogs --disable-infobars \
  --no-first-run --disable-translate --disable-features=Translate \
  --ozone-platform=wayland --user-data-dir="${XDG_RUNTIME_DIR:-/tmp}/seniorvoice-kiosk" \
  "$URL"
