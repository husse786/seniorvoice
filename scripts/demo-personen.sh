#!/usr/bin/env bash
# Legt die Demo-Personen an (Frau Keller, Sandra Keller, Projektteam) und
# richtet Gerät und Portal so ein, dass sie zusammenpassen. Darf mehrfach
# laufen: Vorhandenes bleibt unverändert. Anleitung: docs/simulation.md
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[ -f .env ] || { cp .env.example .env; chmod 600 .env; }
set -a; . ./.env; [ -f portal/.env ] && . portal/.env; set +a
PY="${PYTHON:-$ROOT/.venv/bin/python}"
[ -x "$PY" ] || PY="$(command -v python3)"
exec "$PY" scripts/demo_personen.py
