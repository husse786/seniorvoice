#!/usr/bin/env bash
# Ganze Kette auf einem Rechner: Portal + simuliertes Gerät.
#   Portal:              http://127.0.0.1:8780
#   Simuliertes Telefon: http://127.0.0.1:8771
# Anleitung: docs/portal.md (Abschnitt «Demo auf einem Rechner»).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
"$ROOT/scripts/start-portal.sh" &
PORTAL_PID=$!
trap 'kill "$PORTAL_PID" 2>/dev/null || true' EXIT INT TERM
sleep 1
if ! kill -0 "$PORTAL_PID" 2>/dev/null; then
  echo "Portal startet nicht (Port belegt?)" >&2
  exit 1
fi
"$ROOT/scripts/start-simulation.sh"
