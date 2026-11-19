# Simuliertes Gerät (Mac oder Pi)

Status: Entwurf, in der Cloud-Testumgebung durchgespielt (Textmodus, Termin aus der Geräte-API klingelt, Abheben bestätigt). Auf einem Mac und auf dem Pi noch nicht geprüft.

## Wozu

Solange das Telefon (Gabel, Knöpfe, Hörer) nicht zusammengebaut ist, läuft die **echte Gerätesoftware** auf einem Mac oder auf dem Pi 5. Nur drei Dinge sind ersetzt:

| Echt am Telefon | In der Simulation |
|---|---|
| Gabelschalter und 6 Knöpfe (GPIO) | Telefon-Seite im Browser: `http://127.0.0.1:8771` |
| Hörer und Raumlautsprecher | Mikrofon und Lautsprecher des Rechners, **oder** Textmodus |
| Handy der Help-Kontaktperson | Feld «Kontakt-Handy» auf der Telefon-Seite mit Knopf «Ich kümmere mich» |

Alles andere ist derselbe Code wie später am Telefon: Kern und Gesprächsprozess (A12), Erinnerungen mit Klingeln (A5/A6), Help mit Eskalation (A13/A14), Rat (B2), Gedächtnis mit 7-Tage-Frist (A8), Geräte-API für das Portal (B4) und die Messwerte für den Gerätezustand.

Derselbe Code läuft auf dem Pi (`docs/pi-einrichten.md`): Dort startet ihn der Dienst mit `SENIORVOICE_INPUT=web`, bis Gabel und Knöpfe verdrahtet sind; danach mit `gpio`.

## Zwei Betriebsarten

- **Ton** (`SIM_AUDIO=audio`, Standard): Sprechen ins Mikrofon, Antworten aus dem Lautsprecher. Braucht Whisper und Piper.
- **Text** (`SIM_AUDIO=text`): Tippen statt Sprechen, Antworten als Text auf der Seite. Braucht weder Mikrofon noch Lautsprecher, nur das Sprachmodell. Gut für Präsentationen im Raum und als Rückfall, falls der Ton nicht klappt.

Datenschutz wie am Gerät: Getippter Text und Antworten stehen nur im Arbeitsspeicher und verschwinden beim Auflegen von der Seite. Nichts davon kommt in eine Datei, ein Log oder die Messwerte (A8, F1). Die Telefon-Seite ist nur von diesem Rechner aus erreichbar (127.0.0.1).

## Einrichten auf dem Mac (einmal)

1. **Python 3.11 oder neuer** und **Ollama** installieren (ollama.com, App für macOS). Dann das Modell laden:
   ```bash
   ollama pull gemma3:1b
   ```
2. Code und virtuelle Umgebung:
   ```bash
   git clone https://github.com/husse786/seniorvoice.git && cd seniorvoice
   python3 -m venv .venv && . .venv/bin/activate
   pip install -r pipeline/requirements.txt
   ```
3. Nur für den Ton-Modus: Stimme für Piper (Piper ist ab Version 1.8 auch für Apple-Chips als fertiges Paket verfügbar):
   ```bash
   pip install piper-tts
   python -m piper.download_voices --data-dir ~/.local/share/piper-voices de_DE-thorsten-medium
   ```
   Beim ersten Start fragt macOS, ob das Terminal das Mikrofon benutzen darf: erlauben.
4. Konfiguration und Gerätetoken:
   ```bash
   cp .env.example .env
   cd pipeline && python device_api_cli.py token
   ```
   Die ausgegebene Zeile `DEVICE_API_TOKEN_SHA256=…` in `.env` eintragen. Den Token selbst für das Portal aufheben. In `.env` zusätzlich:
   ```
   AUDIO_DEVICE_NAME=
   SIM_AUDIO=text
   SENIOR_NAME="Frau Keller"
   ```
   (`AUDIO_DEVICE_NAME` leer = eingebautes Mikrofon. Werte mit Leerzeichen in Anführungszeichen.)
5. Freigaben für das Portal (wie am echten Gerät mit Zustimmung der Seniorin/des Seniors):
   ```bash
   python device_api_cli.py grant sandra.keller "Sandra Keller" angehoerige --help-visible --senior-consent
   python device_api_cli.py grant admin.team "Projektteam" admin --senior-consent
   ```
6. Help-Kontakt eintragen (sonst sagt das Gerät nach dem Help-Knopf sofort «Bitte rufen Sie 144 an»):
   ```bash
   python contacts_cli.py set "Sandra Keller|Tochter|Sandra" "Spitex Winterthur|Spitex|Spitex"
   ```
   Im Testkanal `console` ist die Adresse nur eine Bezeichnung.

## Starten

```bash
scripts/start-simulation.sh                  # Modus aus .env
SIM_AUDIO=text scripts/start-simulation.sh   # Textmodus für diesen Start
```

Dann `http://127.0.0.1:8771` im Browser öffnen. Beenden mit Ctrl+C.

## Demo-Ablauf (Z7: Termin im Portal kommt am Gerät an)

1. Portal öffnen (`docs/portal.md`) und als Angehörige einen Termin in 2 Minuten eintragen.
2. Zur vollen Minute klingelt die Telefon-Seite («Es klingelt – bitte abheben»), im Ton-Modus auch hörbar.
3. «Hörer abheben»: das Gerät sagt die Erinnerung an.
4. Im Portal steht beim Termin jetzt «bestätigt».
5. «Hilfe» drücken: im Feld Kontakt-Handy erscheint die Meldung an die Kontaktperson; «Ich kümmere mich» schliesst den Alarm, das Gerät bestätigt laut.

## Was die Simulation nicht zeigt

- Echte Latenzen des Pi: Ein Mac rechnet deutlich schneller. Werte für die Präsentation oder den Bericht nur vom Pi nehmen.
- Gabel und Knöpfe als Hardware (Entprellung, Verdrahtung): getestet nur mit Software-Tests (`tests/test_telephone_hardware.py`).
- Zustellung über Telegram: Die Simulation nutzt den Testkanal `console` (F4 offen).
