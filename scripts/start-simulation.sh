#!/usr/bin/env bash
# Startet das simulierte Gerät auf diesem Rechner (Mac oder Pi):
# Geräte-API für das Portal und das Telefon (Kern + Gespräch) mit der
# Telefon-Seite im Browser statt Gabel und Knöpfen. Anleitung: docs/simulation.md
#
#   scripts/start-simulation.sh            sprechen und tippen (Ton automatisch, wenn vorhanden)
#   SIM_AUDIO=text scripts/start-simulation.sh   nur tippen
#
# Beenden mit Ctrl+C (stoppt beide Dienste).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OVERRIDE_SIM_AUDIO="${SIM_AUDIO:-}"
if [ -f .env ]; then
  set -a; . ./.env; set +a
fi
if [ -n "$OVERRIDE_SIM_AUDIO" ]; then export SIM_AUDIO="$OVERRIDE_SIM_AUDIO"; fi
PY="${PYTHON:-$ROOT/.venv/bin/python}"
[ -x "$PY" ] || PY="$(command -v python3)"
export PATH="$ROOT/.venv/bin:$PATH"     # piper aus der virtuellen Umgebung

cd pipeline
"$PY" device_api.py &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT INT TERM
sleep 1
if ! kill -0 "$API_PID" 2>/dev/null; then
  echo "Geräte-API startet nicht: zuerst scripts/demo-personen.sh ausführen (docs/simulation.md, Schritt 3)" >&2
  exit 1
fi
echo
echo "  Simuliertes Telefon:  http://127.0.0.1:${SIM_PHONE_PORT:-8771}"
echo "  Geräte-API:           ${DEVICE_API_HOST:-127.0.0.1}:${DEVICE_API_PORT:-8770}"
echo "  Ton:                  ${SIM_AUDIO:-auto} (auto = wenn Mikrofon und Stimme da sind)"
echo
"$PY" core_service.py --input web
