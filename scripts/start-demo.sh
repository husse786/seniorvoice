#!/usr/bin/env bash
# Ganze Kette auf einem Rechner: Portal + simuliertes Gerät.
#   Portal:              http://127.0.0.1:8780
#   Simuliertes Telefon: http://127.0.0.1:8771
# Sprechen und Tippen gehen beide; der Ton wird beim Start automatisch gewählt.
#   scripts/start-demo.sh                  alles starten
#   SIM_AUDIO=text scripts/start-demo.sh   nur tippen, für diesen Start
# Erste Einrichtung und ältere .env erledigt scripts/vorbereiten.sh.
# Anleitung: docs/simulation.md. Beenden mit Ctrl+C.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
"$ROOT/scripts/vorbereiten.sh"
export SV_VORBEREITET=1
"$ROOT/scripts/start-portal.sh" &
PORTAL_PID=$!
trap 'kill "$PORTAL_PID" 2>/dev/null || true' EXIT INT TERM
sleep 1
if ! kill -0 "$PORTAL_PID" 2>/dev/null; then
  echo "Portal startet nicht (Port belegt?)" >&2
  exit 1
fi
"$ROOT/scripts/start-simulation.sh"
