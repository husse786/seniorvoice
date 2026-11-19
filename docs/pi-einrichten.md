# Pi 5 als Gerät am Portal einrichten

Status: Entwurf, noch nicht auf dem Pi durchgespielt (Einrichtungsskript und Hardwareerkennung in der Cloud mit Testdaten geprüft). Der Code ist derselbe wie in der Simulation auf dem Mac (`docs/simulation.md`), die dort getestet ist.

Ziel: Der Pi ist das echte Gerät, das Portal läuft auf dem Team-Laptop, beide sind per WireGuard verbunden. Solange Hörer, Gabel und Knöpfe nicht verdrahtet sind, bedient man das Gerät über die Telefon-Seite im Browser des Laptops; Mikrofon und Ton laufen aber schon am Pi.

## Voraussetzung

[setup-schnellstart.md](setup-schnellstart.md) Schritte 1 bis 3 sind erledigt: Raspberry Pi OS **Lite** (64 bit) läuft, SSH geht, der Code liegt in `~/seniorvoice`.

## 0. Einrichten mit einem Befehl (auf dem Pi)

```bash
cd ~/seniorvoice && scripts/pi-einrichten.sh
```

Das Skript installiert Programme, Python-Pakete, Sprachmodell und Stimme, legt `.env` an, erkennt die angeschlossene Hardware und trägt sie ein, richtet die Dienste ein (Telefon, Geräte-API, Bildschirm) und macht am Ende den Selbsttest. Es darf beliebig oft laufen, zum Beispiel nach jedem neuen Teil. `scripts/pi-einrichten.sh --trocken` zeigt nur, was es tun würde.

Was es erkennt (`scripts/hardware_erkennen.py`, allein aufrufbar):

| Teil | Erkannt an | Eintrag in `.env` |
|---|---|---|
| GPIO-Chip des Pi 5 | `gpiodetect`, Zeile `pinctrl-rp1` | `GPIO_CHIP` |
| Hörer und Raumlautsprecher | Tonkarten «handset» und «speaker» (udev-Regel, [inbetriebnahme-telefon.md](inbetriebnahme-telefon.md) 4.3); vorher eine einzelne USB-Tonkarte für beides | `HANDSET_ALSA_DEVICE`, `SPEAKER_ALSA_DEVICE` |
| Webcam-Mikrofon | Tonkarte «C920» | `AUDIO_DEVICE_NAME` |
| Bildschirm | Touch Display 2 am DSI-Anschluss oder HDMI | Bildschirm-Dienst an |

Werte, die jemand in `.env` selbst gesetzt hat, ändert es nie; es meldet nur, was es erkannt hätte. Gabel und Knöpfe lassen sich nicht automatisch erkennen: Prüfung von Hand in [inbetriebnahme-telefon.md](inbetriebnahme-telefon.md) 4.2.

Danach fehlen nur noch die Schritte, die eine Zustimmung oder den Laptop brauchen: 1 (Token, Freigaben), 2 (Tunnel) und 4 (Portal).

## 1. Gerätetoken und Freigaben (auf dem Pi)

```bash
cd ~/seniorvoice/pipeline && . ../.venv/bin/activate
python device_api_cli.py token
```
Die Zeile `DEVICE_API_TOKEN_SHA256=…` in `~/seniorvoice/.env` eintragen. Den Token selbst im Passwortspeicher ablegen; das Portal braucht ihn (Schritt 4).

Freigaben, mit Zustimmung der Seniorin/des Seniors (die Logins müssen zu den Portal-Konten passen):
```bash
python device_api_cli.py grant sandra.keller "Sandra Keller" angehoerige --help-visible --senior-consent
python device_api_cli.py grant admin.team "Projektteam" admin --senior-consent
```
Help-Kontakte (T3: bei der Einrichtung, mit Zustimmung):
```bash
python contacts_cli.py set "Sandra Keller|Tochter|Sandra" "Spitex Winterthur|Spitex|Spitex"
```

## 2. Tunnel

[wireguard.md](wireguard.md), Schritte 1 bis 4. Danach in `~/seniorvoice/.env`:
```
DEVICE_API_HOST=10.77.0.2
```

## 3. Autostart

Solange die Telefon-Hardware fehlt, in `~/seniorvoice/.env`:
```
SENIORVOICE_INPUT=web
SIM_PHONE_HOST=10.77.0.2
```
(Sobald Gabel und Knöpfe verdrahtet sind: beide Zeilen löschen. Dann gilt `gpio` aus dem Dienst.)

Die Dienste richtet `scripts/pi-einrichten.sh` ein (Schritt 0), passend zum Benutzernamen und Ordner. Nach einer Änderung an `.env` oder dem Gerätetoken das Skript nochmals laufen lassen oder neu starten:
```bash
sudo systemctl restart seniorvoice seniorvoice-api
journalctl -u seniorvoice -f       # Ctrl+C beendet nur die Anzeige
```

## 3a. Bildschirm (Touch Display 2, T11)

Das Gerät zeigt auf `http://127.0.0.1:8772` dieselbe Bildschirm-Seite wie das gezeichnete Telefon in der Simulation: Uhr, Termine von heute, Erinnerung beim Klingeln, das laufende Gespräch und den Hilfe-Status. Die Seite ist nur auf dem Pi selbst erreichbar und nur zum Anschauen, ohne Bedienung.

Dafür braucht es **keinen Desktop**. Der Dienst `seniorvoice-screen` startet auf Raspberry Pi OS Lite den Kiosk-Fenstermanager **cage** und darin Chromium im Vollbild (`scripts/bildschirm-kiosk.sh`). `scripts/pi-einrichten.sh` installiert beides und schaltet den Dienst ein, sobald ein Bildschirm angeschlossen ist.

- **Strom:** Das Touch Display 2 bekommt Strom über die Stiftleiste, Stift 2 (5 V, rot) und Stift 6 (GND, schwarz), laut Raspberry-Pi-Doku. Das Flachkabel kommt an den DSI-Anschluss des Pi. Der Pi erkennt das Display von selbst.
- **Quer statt hochkant:** Das Display ist von Haus aus hochkant. Der Kiosk dreht es mit `SCREEN_ROTATE=90` (Standard). Steht das Bild auf dem Kopf: `SCREEN_ROTATE=270` in `.env`, dann `sudo systemctl restart seniorvoice-screen`.
- **Ohne Bildschirm:** Der Dienst bleibt aus, das Gerät läuft normal. Ganz abschalten: `SCREEN_ENABLED=false` in `.env`.

Noch nicht auf dem Pi geprüft (Display noch nicht gekauft). Datenschutz: Während eines Gesprächs stehen die letzten Sätze auf dem Bildschirm. Wer daneben sitzt, kann mitlesen. Beim Auflegen sind sie weg. Chromium läuft ohne Verlauf und Cache auf der Karte.

## 4. Portal auf dem Mac

```bash
cd portal
python portal_cli.py add-device keller "Telefon Frau Keller" "Frau Keller" http://10.77.0.2:8770
python portal_cli.py assign sandra.keller keller
../scripts/start-portal.sh
```
Konten anlegen wie in [portal.md](portal.md), Schritt 1. Auf dem Mac läuft für die Demo nur noch das Portal, nicht mehr die Simulation.

Im Browser des Mac:
- Portal: `http://127.0.0.1:8780`
- Telefon-Seite des Pi: `http://10.77.0.2:8771`

## 5. Prüfen

Auf dem Pi:
```bash
scripts/check-device.sh
```
Alles «OK» oder begründete «WARNUNG». Dann der Demo-Ablauf aus `docs/simulation.md`: Termin im Portal, Telefon-Seite klingelt (und der Lautsprecher am Pi), abheben, im Portal «bestätigt». In der Technik-Ansicht (Admin) stehen jetzt die echten Werte des Pi: Temperatur, Speicher, Antwortzeiten.

## Was der Pi gegenüber der Simulation zeigt

- Echte Antwortzeiten (Spracherkennung und Sprachmodell auf dem Pi). Nur diese Werte gehören in Präsentation und Bericht.
- Temperatur und Drosselung unter Last.
- Ton über Webcam-Mikrofon und USB-Lautsprecher.
