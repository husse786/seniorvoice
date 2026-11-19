# Pi 5 als Gerät am Portal einrichten

Status: Entwurf, noch nicht auf dem Pi durchgespielt. Der Code ist derselbe wie in der Simulation auf dem Mac (`docs/simulation.md`), die dort getestet ist.

Ziel: Der Pi ist das echte Gerät, das Portal läuft auf dem Team-Laptop, beide sind per WireGuard verbunden. Solange Hörer, Gabel und Knöpfe nicht verdrahtet sind, bedient man das Gerät über die Telefon-Seite im Browser des Laptops; Mikrofon und Ton laufen aber schon am Pi.

## Voraussetzung

[setup-schnellstart.md](setup-schnellstart.md) Schritte 1 bis 6 sind erledigt: Pi läuft, SeniorVoice ist installiert, `core_service.py` antwortet im Terminal.

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

```bash
cd ~/seniorvoice
sudo cp deploy/seniorvoice.service deploy/seniorvoice-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now seniorvoice-api seniorvoice
journalctl -u seniorvoice -f       # Ctrl+C beendet nur die Anzeige
```

## 3a. Bildschirm (7"-Display, T11)

Das Gerät zeigt auf `http://127.0.0.1:8772` dieselbe Bildschirm-Seite wie das gezeichnete Telefon in der Simulation: Uhr, Termine von heute, Erinnerung beim Klingeln, das laufende Gespräch und den Hilfe-Status. Die Seite ist nur auf dem Pi selbst erreichbar und nur zum Anschauen, ohne Bedienung.

Der Browser des Pi zeigt sie nach dem Anmelden im Vollbild. In `~/.config/labwc/autostart` (Raspberry Pi OS mit Desktop, labwc):
```
chromium-browser --kiosk --noerrdialogs --disable-infobars --incognito http://127.0.0.1:8772/ &
```
(Heisst das Programm auf dem Pi `chromium`, den Namen anpassen.) Ohne Bildschirm: `SCREEN_ENABLED=false` in `.env`.

Noch nicht auf dem Pi geprüft. Datenschutz: Während eines Gesprächs stehen die letzten Sätze auf dem Bildschirm. Wer daneben sitzt, kann mitlesen. Beim Auflegen sind sie weg.

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
