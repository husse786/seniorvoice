# Simuliertes Gerät (Mac oder Pi)

Status: Entwurf. In der Cloud-Testumgebung durchgespielt (nur Tippen, ohne Ton). Ton auf dem Mac und Betrieb auf dem Pi noch nicht geprüft.

## Wozu

Solange das Telefon (Gabel, Knöpfe, Hörer) nicht zusammengebaut ist, läuft die **echte Gerätesoftware** auf einem Mac oder auf dem Pi 5. Nur drei Dinge sind ersetzt:

| Echt am Telefon | In der Simulation |
|---|---|
| Gabelschalter und 6 Knöpfe (GPIO) | Gezeichnetes Telefon im Browser: `http://127.0.0.1:8771`. Hörer anklicken zum Abheben, Tasten drücken |
| 7"-Bildschirm am Gerät | Derselbe Bildschirm, ins gezeichnete Telefon eingesetzt |
| Hörer und Raumlautsprecher | Mikrofon und Lautsprecher des Rechners, dazu immer ein Tippfeld |
| Handy der Hilfe-Kontaktperson | Meldungen im Gesprächsfeld, Knopf «Ich kümmere mich» |

Alles andere ist derselbe Code wie später am Telefon: Kern und Gesprächsprozess (A12), Erinnerungen mit Klingeln (A5/A6), Help mit Eskalation (A13/A14), Rat (B2), Gedächtnis mit 7-Tage-Frist (A8), Geräte-API für das Portal (B4) und die Messwerte für den Gerätezustand.

Derselbe Code läuft auf dem Pi (`docs/pi-einrichten.md`): Dort startet ihn der Dienst mit `SENIORVOICE_INPUT=web`, bis Gabel und Knöpfe verdrahtet sind; danach mit `gpio`.

## Sprechen und Tippen

Es gibt nichts umzustellen. **Sprechen und Tippen gehen immer gleichzeitig.** Ein getippter Satz ersetzt die nächste gesprochene Antwort. Was das Gerät sagt, ist zu hören und steht zusätzlich als Text da.

Die Taste «Sprechen» unterbricht das Gerät: Es hört sofort auf zu reden und hört zu. Nach mehr als einer Minute Stille sagt es zuerst kurz, wo das Gespräch war («Wo waren wir? Sie hatten gesagt: …»).

Beim Start prüft die Simulation selbst, ob Mikrofon, Whisper und Piper da sind. Fehlt etwas, läuft sie nur mit Tippen weiter, und auf der Seite steht, was fehlt. Ist das Mikrofon aus `.env` (die Webcam C920 des Pi) nicht da, nimmt sie das eingebaute Mikrofon. Hört das Mikrofon nichts, erscheint ein Hinweis im Gesprächsfeld.

Datenschutz wie am Gerät: Gesprochenes, Getipptes und Antworten stehen nur im Arbeitsspeicher und verschwinden beim Auflegen von der Seite und vom Bildschirm. Nichts davon kommt in eine Datei, ein Log oder die Messwerte (A8, F1). Durchsagen über den Lautsprecher und Meldungen an die Kontaktperson bleiben im Gesprächsfeld stehen, bis die Simulation neu startet. Die Seite ist nur von diesem Rechner aus erreichbar (127.0.0.1).

## Einrichten auf dem Mac (einmal)

1. **Python 3.11 oder neuer** (`brew install python@3.12`) und **Ollama** installieren (ollama.com, App für macOS). Dann das Modell laden:
   ```bash
   ollama pull gemma3:1b
   ```
2. Code und virtuelle Umgebung (nicht im iCloud-Ordner, Vorschlag `~/Developer/seniorvoice`):
   ```bash
   git clone https://github.com/husse786/seniorvoice.git && cd seniorvoice
   python3 -m venv .venv
   ```
3. Mikrofon freigeben: macOS fragt beim ersten Start, ob das Terminal das Mikrofon benutzen darf. Erlauben. Falls verpasst: Systemeinstellungen, Datenschutz & Sicherheit, Mikrofon, Terminal einschalten.

Mehr ist nicht einzurichten. Den Rest erledigt der erste Start.

## Starten

```bash
scripts/start-demo.sh
```

Das startet Portal und Telefon zusammen. Dann `http://127.0.0.1:8771` (Telefon) und `http://127.0.0.1:8780` (Portal) im Browser öffnen. Beenden mit Ctrl+C.

Vor jedem Start prüft `scripts/vorbereiten.sh` den Rechner und richtet ein, was fehlt:

| Fall | Was der Start macht |
|---|---|
| Erster Start (keine `.env`, kein Gerätetoken) | legt die Demo-Personen an: Frau Keller, Sandra Keller, Spitex Winterthur, Projektteam, mit Gerätetoken, Freigaben, Hilfe-Kontakten, Beispielterminen und Portal-Konten (`scripts/demo-personen.sh`). Fragt pro Portal-Konto ein Passwort und zeigt den Code-Schlüssel für die Authenticator-App einmal an. Beides gleich sichern, zum Beispiel in der Passwörter-App des Mac |
| `.env` aus einer früheren Einrichtung mit `SIM_AUDIO=text` oder `SIM_AUDIO=audio` | schaltet die Zeile aus und sagt es im Terminal. Eine Kopie der alten Datei bleibt als `.env.vorher-…` liegen |
| Whisper, Piper oder die deutsche Stimme fehlen (Mac) | installiert sie einmal in `.venv` nach. Ohne Internet läuft der Start trotzdem, dann nur mit Tippen |

Im Terminal und unten auf der Telefon-Seite steht danach, was dieser Start benutzt, zum Beispiel «Ton an. Mikrofon: MacBook Pro Microphone. Tippen geht auch.» Ist es das falsche Mikrofon (iPhone, Docking-Station), unter Systemeinstellungen, Ton, Eingabe das richtige wählen und neu starten.

Nur Tippen, zum Beispiel in einem lauten Raum: `SIM_AUDIO=text scripts/start-demo.sh`. Das gilt nur für diesen Start; in `.env` muss dafür nichts stehen.

`scripts/start-simulation.sh` startet nur das Gerät ohne Portal (Pi, oder Portal läuft schon). Es macht vorher dieselbe Prüfung.

## Demo-Ablauf (Z7: Termin im Portal kommt am Gerät an)

1. Portal öffnen (`docs/portal.md`) und als Angehörige einen Termin in 2 Minuten eintragen.
2. Zur vollen Minute klingelt das Telefon: Der Hörer wackelt, der Bildschirm zeigt die Erinnerung, der Klingelton ist hörbar.
3. Hörer anklicken: Er hebt sich ab, und das Gerät sagt die Erinnerung an. Ohne fällige Erinnerung begrüsst es stattdessen mit Namen, nennt den nächsten Termin von heute und stellt eine kleine Frage (Texte: `docs/begruessung-und-persona.md`).
4. Im Portal steht beim Termin jetzt «bestätigt».
5. «Hilfe» drücken: Das Gerät sagt «Ich informiere gleich Sandra …», der Bildschirm zählt 10 Sekunden herunter. Danach steht im Gesprächsfeld die Meldung an die Kontaktperson. «Ich kümmere mich» schliesst den Alarm, das Gerät bestätigt laut.
6. Abbrechen zeigen: «Hilfe» drücken und nach 2 bis 10 Sekunden nochmals «Hilfe». Das Gerät sagt «Abgebrochen …», es geht keine Meldung raus, im Portal steht im Hilfe-Verlauf «abgebrochen».

### Hilfe abbrechen (19.11.2026)

| Was | Verhalten |
|---|---|
| Erster Druck | Meldung wartet 10 Sekunden. Ansage: «Ich informiere gleich …, falls das ein Versehen war, drücken Sie nochmals Hilfe.» |
| Zweiter Druck nach 2 bis 10 Sekunden | Abbruch. Niemand wurde informiert, darum keine Entwarnung nötig. Status «abgebrochen» im Hilfe-Verlauf (30 Tage). |
| Drücke in den ersten 2 Sekunden | zählen nicht (Schutz vor schnellem Mehrfachdrücken in Panik) |
| Druck nach dem Versand | wie bisher: «Ich habe … bereits informiert» |
| Nächster Druck bis 2 Minuten nach einem Abbruch | geht sofort raus und lässt sich nicht abbrechen |
| Neustart | Ein abgebrochener Ruf kommt nicht zurück. Ein noch offener Ruf endet wie bisher mit «Bitte rufen Sie 144 an». |

## Was die Simulation nicht zeigt

- Echte Latenzen des Pi: Ein Mac rechnet deutlich schneller. Werte für die Präsentation oder den Bericht nur vom Pi nehmen.
- Gabel und Knöpfe als Hardware (Entprellung, Verdrahtung): getestet nur mit Software-Tests (`tests/test_telephone_hardware.py`).
- Zustellung per E-Mail: Die Simulation nutzt den Testkanal `console`. Echte Mails: `docs/email-kanal.md`.
