# Tunnel zwischen Portal und Gerät (WireGuard)

Status: Entwurf. Das Skript `scripts/wireguard-configs.sh` ist geprüft (erzeugt gültige Schlüssel und Dateien). Ein echter Tunnel zwischen Mac und Pi ist noch nicht aufgebaut worden; das folgt beim Einrichten des Pi.

## Entscheid (T1, T2, OA-09, 19.11.2026)

- **WireGuard**, ohne Drittfirma. Das Gerät baut die Verbindung selbst auf; beim Senior muss am Router nichts eingestellt werden.
- **Prototyp:** Der **Team-Laptop** ist der Hub. Auf ihm läuft das Portal. Kein Server, keine Domain. Grund: Die Nutzertests sind begleitete Sitzungen mit dem Laptop vor Ort; es bleibt nichts bei Seniorinnen und Senioren.
- **Produktivbetrieb:** Der Hub zieht auf einen kleinen Server in der Schweiz, mit Domain und HTTPS (Abschnitt unten). Das ist nur Konfiguration, kein neuer Code.
- Rückfall, falls WireGuard in einem Netz blockiert ist: Tailscale (End-zu-End verschlüsselt, Gratis-Plan).

```
 Browser ──(lokal)── Portal :8780 ── Team-Laptop 10.77.0.1 ══WireGuard══ Pi 10.77.0.2
                                                                  ├─ Geräte-API :8770
                                                                  └─ Telefon-Seite :8771 (nur ohne Telefon-Hardware)
```

Adressen: Laptop `10.77.0.1`, Geräte ab `10.77.0.2`. Port UDP `51820` auf dem Laptop.

## 1. Schlüssel erzeugen (einmal, auf dem Mac)

```bash
brew install wireguard-tools
scripts/wireguard-configs.sh <Adresse-des-Mac>      # z. B. 192.168.1.23
```

Die Adresse des Mac im WLAN steht unter Systemeinstellungen → WLAN → Details → TCP/IP. Mehrere Geräte: zweite Zahl angeben (`… 192.168.1.23 3`).

Die Dateien landen in `~/seniorvoice-wireguard/` (nur für dich lesbar). Sie enthalten private Schlüssel: **nie ins Repo, nie per Chat verschicken**. Für das Team im Passwortspeicher ablegen.

## 2. Mac als Hub

1. **WireGuard** aus dem Mac App Store installieren.
2. «Tunnel aus Datei importieren» → `hub-laptop.conf` → aktivieren.
3. Falls macOS fragt, eingehende Verbindungen für WireGuard erlauben.

## 3. Pi als Gerät

```bash
sudo apt install -y wireguard-tools
# geraet-2.conf vom Mac auf den Pi kopieren (im Mac-Terminal):
#   scp ~/seniorvoice-wireguard/geraet-2.conf pi@seniorvoice.local:/tmp/
sudo install -m 600 /tmp/geraet-2.conf /etc/wireguard/wg0.conf && rm /tmp/geraet-2.conf
sudo systemctl enable --now wg-quick@wg0
ping -c 3 10.77.0.1        # Antwort vom Mac = Tunnel steht
```

In `~/seniorvoice/.env` auf dem Pi:
```
DEVICE_API_HOST=10.77.0.2
```

Im Portal auf dem Mac das Gerät mit dieser Adresse eintragen (`docs/portal.md`):
```bash
python portal_cli.py add-device keller "Telefon Frau Keller" "Frau Keller" http://10.77.0.2:8770
```

**Wenn der Mac eine andere Adresse bekommt** (anderes WLAN, z. B. Hotspot im Testraum), auf dem Pi:
```bash
sudo sed -i 's/^Endpoint = .*/Endpoint = <neue-Adresse>:51820/' /etc/wireguard/wg0.conf
sudo systemctl restart wg-quick@wg0
```
Am einfachsten bleibt es, wenn Mac und Pi immer im selben Netz sind, zum Beispiel im Hotspot des Handys: Dann bleibt die Adresse des Mac meist gleich.

## 4. Firewall auf dem Pi

Der Pi nimmt Verbindungen nur über den Tunnel an, SSH zusätzlich aus dem eigenen WLAN:

```bash
sudo apt install -y ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from 192.168.0.0/16 to any port 22 proto tcp     # SSH im WLAN; Bereich an euer Netz anpassen
sudo ufw allow in on wg0 to any port 8770 proto tcp             # Geräte-API für das Portal
sudo ufw allow in on wg0 to any port 8771 proto tcp             # Telefon-Seite, nur solange ohne Telefon-Hardware
sudo ufw allow in on wg0 to any port 3000 proto tcp             # Grafana (nur Team, docs/grafana/README.md)
sudo ufw enable
sudo ufw status verbose
```

Zusätzlich hören Geräte-API und Telefon-Seite selbst nur auf der Tunnel-Adresse oder `127.0.0.1`; `0.0.0.0` lehnen sie ab.

## 5. Prüfen

Auf dem Pi: `scripts/check-device.sh`. Erwartet: «WireGuard wg0: 10.77.0.2/24», «Verbindung zum Laptop vor …s», «Geräte-API läuft auf 10.77.0.2:8770». Im Portal steht das Gerät auf «online».

## Produktivbetrieb (für die Nachfolgegruppe)

Nicht nötig für Demo und Nutzertests. Erst wenn Angehörige oder Spitex von zu Hause aus zugreifen sollen.

1. **Server in der Schweiz mieten.** Gewählt: **Infomaniak** (Genf, Rechenzentren in der Schweiz). Ein «VPS Lite» genügt (1 vCPU, 2 GB RAM; Preis laut Anbieterseite am 19.11.2026 ab CHF 2.70 pro Monat bei Jahreszahlung, monatlich etwas teurer). Alternative bei Infomaniak: Public Cloud mit Abrechnung pro Stunde. Nicht gewählt: Hetzner (Deutschland, günstige Tarife zeitweise ausverkauft), DigitalOcean (US-Firma, CLOUD Act).
2. **Domain** registrieren (z. B. bei Infomaniak) und auf die Server-Adresse zeigen lassen.
3. Auf dem Server: WireGuard mit `hub-laptop.conf` (Adresse `10.77.0.1` bleibt), Portal wie auf dem Laptop, davor **Caddy** als HTTPS-Proxy (holt das Zertifikat selbst):
   ```
   portal.example.ch {
       reverse_proxy 127.0.0.1:8780
   }
   ```
   Im Portal: `PORTAL_ALLOWED_HOSTS=portal.example.ch` und `PORTAL_SECURE_COOKIE=true`.
4. Auf jedem Gerät nur den `Endpoint` in `/etc/wireguard/wg0.conf` auf den Server ändern.
5. Firewall des Servers: offen nur 443/tcp (Portal), 51820/udp (WireGuard), 22/tcp (Admin, am besten nur mit Schlüssel).
6. Datenschutz: Der Server-Anbieter wird Auftragsbearbeiter für das Portal-Verzeichnis (DS-06, DS-14). Inhalte sieht er nicht; die laufen verschlüsselt im Tunnel und werden im Portal nicht gespeichert.
7. Ab dann möglich: Bestätigungslink «Ich kümmere mich» in der Hilfe-Mail, der ins Portal führt (Zusatz zu F4, 19.11.2026).
