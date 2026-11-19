#!/usr/bin/env bash
# Prüft, ob das Gerät (Pi oder Mac mit Simulation) bereit ist.
# Liest nur, ändert nichts. Aufruf im Ordner seniorvoice:
#   scripts/check-device.sh
# Ausgabe: OK / WARNUNG / FEHLT pro Punkt, am Ende eine Zusammenfassung.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
FAIL=0; WARN=0
ok()   { printf '  OK       %s\n' "$1"; }
warn() { printf '  WARNUNG  %s\n' "$1"; WARN=$((WARN+1)); }
bad()  { printf '  FEHLT    %s\n' "$1"; FAIL=$((FAIL+1)); }

if [ -f .env ]; then set -a; . ./.env; set +a; ok ".env vorhanden"; else bad ".env fehlt (cp .env.example .env)"; fi
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] && ok "virtuelle Umgebung .venv" || { bad ".venv fehlt (docs/setup-schnellstart.md, Schritt 4)"; PY="$(command -v python3)"; }
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' && ok "Python $("$PY" -V 2>&1 | cut -d' ' -f2)" || bad "Python 3.11 oder neuer nötig"

echo "Sprache"
OLLAMA="${LLM_API_BASE:-http://127.0.0.1:11434/v1}"; OLLAMA="${OLLAMA%/v1}"; OLLAMA="${OLLAMA%/}"
MODEL="${LLM_MODEL:-gemma3:1b}"
if TAGS="$(curl -s --noproxy '*' -m 3 "$OLLAMA/api/tags")"; then
  ok "Ollama antwortet ($OLLAMA)"
  echo "$TAGS" | grep -q "\"$MODEL" && ok "Modell $MODEL installiert" || bad "Modell $MODEL fehlt (ollama pull $MODEL)"
else
  bad "Ollama antwortet nicht auf $OLLAMA"
fi
if [ "${SIM_AUDIO:-audio}" = "text" ]; then
  ok "Textmodus: Mikrofon, Whisper und Piper nicht nötig"
else
  VOICE="${PIPER_VOICE:-$HOME/.local/share/piper-voices/de_DE-thorsten-medium.onnx}"
  [ -f "$VOICE" ] && ok "Stimme $(basename "$VOICE")" || bad "Stimme fehlt: $VOICE"
  PATH="$ROOT/.venv/bin:$PATH" command -v piper >/dev/null && ok "piper" || bad "piper fehlt (pip install piper-tts)"
  if MICS="$("$PY" -c 'import sounddevice as sd; print("\n".join(d["name"] for d in sd.query_devices() if d["max_input_channels"] > 0))' 2>/dev/null)"; then
    if [ -z "$MICS" ]; then bad "kein Mikrofon gefunden"
    elif [ -n "${AUDIO_DEVICE_NAME:-}" ] && ! echo "$MICS" | grep -qi -- "$AUDIO_DEVICE_NAME"; then
      bad "Mikrofon «$AUDIO_DEVICE_NAME» nicht gefunden. Vorhanden: $(echo "$MICS" | paste -sd ',' -)"
    else ok "Mikrofon: $(echo "$MICS" | grep -i -m1 -- "${AUDIO_DEVICE_NAME:-.}")"; fi
  else
    bad "sounddevice nicht nutzbar (libportaudio2 installiert?)"
  fi
fi

echo "Verbindung zum Portal"
TOKEN_HASH="${DEVICE_API_TOKEN_SHA256:-}"
[[ "$TOKEN_HASH" =~ ^[0-9a-f]{64}$ ]] && ok "Gerätetoken eingerichtet" || bad "DEVICE_API_TOKEN_SHA256 fehlt (python pipeline/device_api_cli.py token)"
HOST="${DEVICE_API_HOST:-127.0.0.1}"; PORT="${DEVICE_API_PORT:-8770}"
if command -v wg >/dev/null && [ "$(uname)" = "Linux" ]; then
  if ip -4 addr show wg0 2>/dev/null | grep -q "inet "; then
    ok "WireGuard wg0: $(ip -4 -o addr show wg0 | awk '{print $4}')"
    LAST="$(sudo -n wg show wg0 latest-handshakes 2>/dev/null | awk '{print $2}' | head -1)"
    if [ -z "$LAST" ]; then warn "Handshake nicht lesbar (sudo nötig: sudo wg show)"
    elif [ "$LAST" = "0" ]; then bad "noch nie Verbindung zum Laptop (Endpoint in /etc/wireguard/wg0.conf? WireGuard auf dem Mac aktiv?)"
    else AGE=$(( $(date +%s) - LAST )); [ "$AGE" -lt 180 ] && ok "Verbindung zum Laptop vor ${AGE}s" || warn "letzte Verbindung zum Laptop vor ${AGE}s"; fi
    [ "$HOST" = "127.0.0.1" ] && warn "DEVICE_API_HOST=127.0.0.1: das Portal auf dem Laptop erreicht das Gerät so nicht (Tunnel-Adresse eintragen)"
  else
    [ "$HOST" = "127.0.0.1" ] && ok "kein Tunnel (Simulation auf einem Rechner)" || bad "wg0 ist nicht aktiv, DEVICE_API_HOST=$HOST braucht ihn (sudo systemctl start wg-quick@wg0)"
  fi
fi
CODE="$(curl -s --noproxy '*' -m 3 -o /dev/null -w '%{http_code}' "http://$HOST:$PORT/v1/status")"
case "$CODE" in
  401) ok "Geräte-API läuft auf $HOST:$PORT (verlangt Token)";;
  000) bad "Geräte-API antwortet nicht auf $HOST:$PORT";;
  *)   warn "Geräte-API antwortet mit $CODE";;
esac
DBFILE="$(cd pipeline && "$PY" -c 'import config; print(config.MEMORY_DB_PATH)' 2>/dev/null)"
if [ -n "$DBFILE" ] && [ -f "$DBFILE" ]; then
  GRANTS="$(cd pipeline && "$PY" device_api_cli.py list 2>/dev/null | grep -c . || true)"
  [ "${GRANTS:-0}" -gt 0 ] && ok "Freigaben am Gerät: $GRANTS Zeile(n) (python pipeline/device_api_cli.py list)" || warn "keine Freigaben am Gerät (device_api_cli.py grant ...)"
fi

echo "Dienste"
if command -v systemctl >/dev/null && [ "$(uname)" = "Linux" ]; then
  for s in ollama seniorvoice seniorvoice-api wg-quick@wg0; do
    st="$(systemctl is-active "$s" 2>/dev/null)"
    [ "$st" = "active" ] && ok "$s läuft" || warn "$s: ${st:-unbekannt}"
  done
  INPUT="${SENIORVOICE_INPUT:-gpio}"
  ok "Eingabe beim Autostart: $INPUT"
  if [ "$INPUT" = "web" ]; then
    SIMH="${SIM_PHONE_HOST:-127.0.0.1}"
    [ "$SIMH" = "127.0.0.1" ] && warn "Telefon-Seite nur auf dem Pi selbst (SIM_PHONE_HOST=10.77.0.x, damit der Laptop sie öffnet)" \
      || ok "Telefon-Seite für den Laptop: http://$SIMH:${SIM_PHONE_PORT:-8771}"
  fi
  if command -v vcgencmd >/dev/null; then
    T="$(vcgencmd measure_temp | tr -dc '0-9.')"; ok "Temperatur ${T} °C"
    [ "$(vcgencmd get_throttled)" = "throttled=0x0" ] && ok "keine Drosselung" || warn "$(vcgencmd get_throttled) (Netzteil, Kühlung prüfen)"
  fi
fi
STATUS="$(cd pipeline && "$PY" -c 'import config; print(config.STATUS_FILE)' 2>/dev/null)"
if [ -n "$STATUS" ] && [ -f "$STATUS" ]; then
  AGE=$(( $(date +%s) - $("$PY" -c "import json,sys; print(int(json.load(open(sys.argv[1]))['updated']))" "$STATUS" 2>/dev/null || echo 0) ))
  [ "$AGE" -lt 20 ] && ok "Kern läuft (Status vor ${AGE}s)" || warn "Kern-Status ist ${AGE}s alt: Kern läuft nicht?"
else
  warn "Kern hat noch keinen Status geschrieben (läuft er?)"
fi

echo
if [ "$FAIL" -eq 0 ]; then echo "Bereit ($WARN Warnung(en))."; else echo "$FAIL Punkt(e) fehlen, $WARN Warnung(en)."; fi
exit $([ "$FAIL" -eq 0 ] && echo 0 || echo 1)
