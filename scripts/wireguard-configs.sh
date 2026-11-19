#!/usr/bin/env bash
# Erzeugt die WireGuard-Konfiguration: Team-Laptop = Hub (10.77.0.1),
# Geräte = 10.77.0.2, .3, ... Das Gerät wählt sich beim Laptop ein.
# Anleitung: docs/wireguard.md
#
#   scripts/wireguard-configs.sh <Adresse-des-Laptops> [Anzahl-Geräte]
#   scripts/wireguard-configs.sh 192.168.1.23
#   scripts/wireguard-configs.sh husey-mac.local 2
#
# Schreibt nach ~/seniorvoice-wireguard/ (nur für dich lesbar, nie ins Repo):
#   hub-laptop.conf   in die WireGuard-App auf dem Mac importieren
#   geraet-2.conf     auf den Pi als /etc/wireguard/wg0.conf
# Braucht das Programm «wg» (Mac: brew install wireguard-tools).
set -euo pipefail
ENDPOINT="${1:-}"
COUNT="${2:-1}"
PORT="${WG_PORT:-51820}"
OUT="${WG_OUT:-$HOME/seniorvoice-wireguard}"
if [ -z "$ENDPOINT" ] || ! [[ "$COUNT" =~ ^[0-9]+$ ]] || [ "$COUNT" -lt 1 ] || [ "$COUNT" -gt 50 ]; then
  sed -n 2,13p "$0"; exit 1
fi
command -v wg >/dev/null || { echo "wg fehlt (Mac: brew install wireguard-tools, Pi: sudo apt install wireguard-tools)" >&2; exit 1; }
umask 077
mkdir -p "$OUT"
if [ -e "$OUT/hub-laptop.conf" ]; then
  echo "$OUT/hub-laptop.conf gibt es schon. Neue Schlüssel nur bewusst: Ordner vorher umbenennen." >&2
  exit 1
fi
HUB_KEY="$(wg genkey)"
HUB_PUB="$(printf '%s' "$HUB_KEY" | wg pubkey)"
{
  echo "# SeniorVoice: Team-Laptop als Hub. Nur Geräte unten dürfen sich verbinden."
  echo "[Interface]"
  echo "Address = 10.77.0.1/24"
  echo "ListenPort = $PORT"
  echo "PrivateKey = $HUB_KEY"
} > "$OUT/hub-laptop.conf"
for i in $(seq 2 $((COUNT + 1))); do
  KEY="$(wg genkey)"
  PUB="$(printf '%s' "$KEY" | wg pubkey)"
  {
    echo ""
    echo "[Peer]"
    echo "# Gerät 10.77.0.$i"
    echo "PublicKey = $PUB"
    echo "AllowedIPs = 10.77.0.$i/32"
  } >> "$OUT/hub-laptop.conf"
  {
    echo "# SeniorVoice-Gerät 10.77.0.$i. Auf dem Pi: /etc/wireguard/wg0.conf"
    echo "[Interface]"
    echo "Address = 10.77.0.$i/24"
    echo "PrivateKey = $KEY"
    echo ""
    echo "[Peer]"
    echo "# Team-Laptop (Hub). Endpoint ändern, wenn der Laptop eine andere Adresse hat."
    echo "PublicKey = $HUB_PUB"
    echo "Endpoint = $ENDPOINT:$PORT"
    echo "# Nur der Laptop ist über den Tunnel erreichbar, kein anderer Verkehr"
    echo "AllowedIPs = 10.77.0.1/32"
    echo "PersistentKeepalive = 25"
  } > "$OUT/geraet-$i.conf"
done
echo "Geschrieben nach $OUT:"
ls -1 "$OUT"
echo
echo "Weiter: docs/wireguard.md, Schritte 2 und 3."
