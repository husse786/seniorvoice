#!/usr/bin/env bash
# Startet das Portal auf dem Team-Laptop (Anleitung: docs/portal.md).
# Einstellungen optional in portal/.env (PORTAL_HOST, PORTAL_PORT, PORTAL_DB).
# Beenden mit Ctrl+C.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/portal"
if [ -f .env ]; then
  set -a; . ./.env; set +a
fi
PY="${PYTHON:-$ROOT/.venv/bin/python}"
[ -x "$PY" ] || PY="$(command -v python3)"
exec "$PY" server.py
