# Inbetriebnahme Telefon-Hardware (HS26)

Status: Entwurf, am Gerät noch nicht geprüft. Alles hier ist aus dem Code abgeleitet (Stand PR #7); Werte, die erst am Gerät feststehen, sind markiert.

Ziel: Wenn die Teile da sind, nur noch verkabeln, Prüfbefehle laufen lassen, `.env` ausfüllen, testen.

---

## 1. Was der Code erwartet

| Teil | Erwartung im Code | Einstellung |
|---|---|---|
| Gabelschalter | Schalter zwischen GPIO und GND, interner Pull-up. Abgehoben = HIGH | `HOOK_GPIO_PIN`, `HOOK_OFFHOOK_LEVEL` |
| 6 Knöpfe | je Knopf ein Taster zwischen GPIO und GND, interner Pull-up. Gedrückt = LOW, ausgelöst beim Drücken | `BUTTON_PINS` |
| Hörer-Mikrofon | Eingang, den `sounddevice` unter einem eindeutigen Namen findet | `AUDIO_DEVICE_NAME` (Teil des Namens) |
| Hörer-Kapsel | eigener ALSA-Ausgang, nur Gespräch | `HANDSET_ALSA_DEVICE` |
| Raumlautsprecher | eigener ALSA-Ausgang, nur Klingeln, Help-Bestätigung, «Bitte Hörer abheben» | `SPEAKER_ALSA_DEVICE` |

Entprellung 30 ms, Abfrage alle 10 ms. Ist ein Ausgang gesetzt und `aplay` fehlt, bricht die Wiedergabe ab (kein Ausweichen auf den Standard-Ausgang, damit Gesprochenes nie im Raum landet).

**Wichtig: Der Pi 5 hat keine 3,5-mm-Audiobuchse.** Hörer und Lautsprecher brauchen deshalb **zwei getrennte USB-Audio-Adapter** (oder einen Adapter plus einen USB-Lautsprecher mit eigener Soundkarte). Die FS26-Anleitung (`how-to_analog-telephone.md`, Schritt 2.2 «Pi 3.5mm Audioausgang») gilt für den Pi 5 so nicht.

## 2. Verkabelungsplan (Vorschlag = Standardwerte im Code)

Alle Taster und die Gabel schalten nach **GND**. Nie 5 V an einen GPIO-Pin legen (GPIO verträgt nur 3,3 V).

| Funktion | GPIO | Stift (physisch) | GND-Stift daneben |
|---|---|---|---|
| Gabel | GPIO17 | 11 | 9 |
| Sprechen | GPIO5 | 29 | 30 |
| Heute | GPIO6 | 31 | 30 |
| Kalender | GPIO13 | 33 | 34 |
| Rat | GPIO19 | 35 | 34 |
| Familie | GPIO26 | 37 | 39 |
| Hilfe | GPIO21 | 40 | 39 |
| PAM8403 Versorgung | 5 V | 2 oder 4 | 6 |

```
            3V3  (1) (2)  5V   ── PAM8403 +5V
                 (3) (4)  5V
                 (5) (6)  GND  ── PAM8403 GND
                 (7) (8)
            GND  (9) (10)
Gabel ── GPIO17 (11) (12)
                 ...
                (27) (28)      (ID-EEPROM des HAT, frei lassen)
Sprechen GPIO5  (29) (30) GND  ── Sprechen, Heute
Heute    GPIO6  (31) (32)
Kalender GPIO13 (33) (34) GND  ── Kalender, Rat
Rat      GPIO19 (35) (36)
Familie  GPIO26 (37) (38)
            GND (39) (40) GPIO21  Hilfe
             └── Familie, Hilfe
```

Hinweise:
- **Arcade-Taster:** Anschlüsse «COM» und «NO» verwenden. LED-Anschlüsse (falls vorhanden) nicht an GPIO.
- **Gabel:** Mit dem Multimeter prüfen. FS26: aufgelegt = geschlossen (NC). Dann `HOOK_OFFHOOK_LEVEL=1` (Standard). Ist der Schalter umgekehrt (aufgelegt = offen), `HOOK_OFFHOOK_LEVEL=0` setzen, nicht umlöten.
- **Lange Kabel (über ca. 50 cm):** Bei Fehlauslösungen zusätzlich 10 kΩ von GPIO nach 3,3 V (Stift 1) oder `GPIO_DEBOUNCE_MS` erhöhen.
- **GPIO19 und GPIO21** sind auch I2S-Pins. Mit USB-Audio kein Problem; wird später ein I2S-Verstärker-HAT eingesetzt, Rat und Hilfe auf andere Pins legen (nur `BUTTON_PINS` ändern).
- **PIR-Sensor:** Laut README hängt der FS26-PIR an GPIO17, also am Gabel-Pin. `core_service.py` nutzt den PIR nicht: **PIR abstecken**, bevor die Gabel angeschlossen wird.
- **AI HAT+ 2:** wird über PCIe angeschlossen; die GPIO-Leiste muss oben zugänglich bleiben (Stapel-Stiftleiste). Beim Auspacken prüfen, ob die Leiste mitgeliefert wird und ins Gehäuse passt.

### Audio

```
Hörer-Mikrofon ──► USB-Adapter A (Mic-In)           = "handset"
Hörer-Kapsel   ◄── USB-Adapter A (Kopfhörer-Out)    direkt; nur falls zu leise: PAM8403 Nr. 1 dazwischen
Lautsprecher   ◄── PAM8403 Nr. 2 ◄── USB-Adapter B (Kopfhörer-Out) = "speaker"
```

- Hörer-Kapsel zuerst **ohne Verstärker** am Kopfhörer-Ausgang testen (Lautstärke in `alsamixer` klein beginnen). Ein Verstärker direkt am Ohr kann sehr laut werden. Falls doch nötig: eigenes PAM8403 nur für die Kapsel, Poti klein.
- PAM8403-Ausgänge nie mit GND verbinden (Brückenausgang); Lautsprecher zwischen L+ und L−.
- Ein PAM8403 für beide Ausgänge geht technisch, aber das Poti regelt beide Kanäle gleich. Deshalb zwei Module.
- Mikrofon: FS26-Belegung in `how-to_analog-telephone.md` Schritt 1.3 und 2.1. Alte Kohlemikrofone liefern mit Mic-Bias kaum Signal; dann Elektret-Kapsel einsetzen.

## 3. Jetzt schon vorbereiten (ohne Teile)

1. **System:** Raspberry Pi OS **Lite** 64-bit empfohlen (ohne Desktop greift kein PulseAudio/PipeWire auf die Audiogeräte zu). Läuft der FS26-Pi mit Desktop weiter, siehe Fehlerbehebung «Device or resource busy».
2. **Benutzername** beim Einrichten notieren. Der Dienst `deploy/seniorvoice.service` nimmt `pi` und `/home/pi/seniorvoice` an; sonst `User=` und alle Pfade anpassen.
3. **Code und Umgebung:**
   ```bash
   git clone https://github.com/husse786/seniorvoice.git ~/seniorvoice
   cd ~/seniorvoice
   python3 -m venv --system-site-packages .venv   # system-site-packages: lgpio kommt vom System
   . .venv/bin/activate
   pip install -r pipeline/requirements.txt piper-tts
   python -c "import lgpio; print('lgpio ok')"
   which aplay arecord pinctrl                     # alle drei müssen gefunden werden
   ```
4. **Modelle:** `ollama pull gemma3:1b` (oder das Team-Modell), Piper-Stimme `de_DE-thorsten-medium` nach `~/.local/share/piper-voices/`.
5. **Ablauf ohne Hardware prüfen:** `cd pipeline && python core_service.py` (Tastatur: `a` abheben, `h` auflegen, `heute`, `hilfe` …). Läuft das, ist nach Lieferung nur noch die Hardware neu.
6. **Testdaten:**
   ```bash
   python contacts_cli.py set "Test Tochter|Tochter|test1" "Test Spitex|Spitex|test2"
   python appointments_cli.py add "Testtermin" "JJJJ-MM-TT HH:MM" --by Test --pre 0
   ```
7. **RTC-Batterie** (wenn geliefert): in `/boot/firmware/config.txt` `dtparam=rtc_bbat_vchg=3000000` ergänzen, damit die offizielle wiederaufladbare Batterie geladen wird. Ohne diese Zeile wird sie nicht geladen.
8. **SSD ins USB-Gehäuse** (wenn AI HAT+ 2 kommt): Die SSD ist eine **Crucial P310, Grösse 2230** (nicht 2280). Das Gehäuse muss NVMe und 2230 aufnehmen. Der Pi 5 bootet ab Werk auch von USB (`rpi-eeprom-config` zeigt `BOOT_ORDER`, darin muss eine `4` stehen).

## 4. Erster Start, Schritt für Schritt

Dienst vorher stoppen, falls installiert: `sudo systemctl stop seniorvoice`.

### 4.1 GPIO-Chip
```bash
gpiodetect            # Zeile mit "pinctrl-rp1" (54 lines) suchen
ls -l /dev/gpiochip*
```
Die Nummer der `pinctrl-rp1`-Zeile in `.env` als `GPIO_CHIP` eintragen (ältere Kernel: 4, neuere: 0).

### 4.2 Gabel und Knöpfe einzeln prüfen (ohne SeniorVoice)
```bash
for p in 17 5 6 13 19 26 21; do pinctrl set $p ip pu; done
watch -n 0.2 'for p in 17 5 6 13 19 26 21; do pinctrl get $p; done'
```
Erwartung: Knöpfe zeigen `hi`, beim Drücken `lo`. Gabel: aufgelegt `lo`, abgehoben `hi` (sonst `HOOK_OFFHOOK_LEVEL=0`). Ändert sich beim Drücken ein anderer Pin, Zuordnung in `BUTTON_PINS` anpassen statt umzulöten.

### 4.3 Audiogeräte benennen
```bash
aplay -l ; arecord -l
```
Damit die Kartennummern nach einem Neustart nicht vertauschen, Karten fest benennen. USB-Pfad je Adapter ermitteln (Adapter am vorgesehenen USB-Port, `N` = Kartennummer aus `aplay -l`):
```bash
udevadm info --attribute-walk /sys/class/sound/cardN | grep -m1 'KERNELS=="[0-9]-'
```
Datei `/etc/udev/rules.d/85-seniorvoice-audio.rules` (Werte `1-1` / `3-1` durch die gefundenen ersetzen):
```
SUBSYSTEM=="sound", KERNEL=="card*", KERNELS=="1-1", ATTR{id}="handset"
SUBSYSTEM=="sound", KERNEL=="card*", KERNELS=="3-1", ATTR{id}="speaker"
```
Dann neu starten; `aplay -l` zeigt jetzt `card X: handset` und `card Y: speaker`. Die Adapter danach immer an denselben Ports lassen.

### 4.4 Ausgänge und Mikrofon testen
```bash
speaker-test -D plughw:CARD=handset,DEV=0 -c 1 -t sine -f 440 -l 1   # Ton nur im Hörer
speaker-test -D plughw:CARD=speaker,DEV=0 -c 1 -t sine -f 440 -l 1   # Ton nur im Raum
arecord -D plughw:CARD=handset,DEV=0 -f S16_LE -r 16000 -c 1 -d 5 /tmp/t.wav
aplay -D plughw:CARD=handset,DEV=0 /tmp/t.wav                        # eigene Stimme im Hörer
alsamixer -c handset    # Pegel einstellen (F4 = Aufnahme), danach: sudo alsactl store
python -c "import sounddevice as sd; print(sd.query_devices())"
```
Im letzten Befehl muss der Hörer-Eingang einen Namen haben, den **kein anderes Gerät** enthält. Diesen Namensteil als `AUDIO_DEVICE_NAME` eintragen. Haben beide Adapter denselben Namen, siehe Fehlerbehebung.

### 4.5 `.env` ausfüllen
```bash
cp .env.example .env   # falls noch nicht vorhanden
```
Kommentare nur auf eigenen Zeilen: systemd liest `# …` hinter einem Wert als Teil des Werts, und der Dienst startet dann nicht. Werte mit Leerzeichen in Anführungszeichen setzen.
```
# aus 4.1
GPIO_CHIP=0
HOOK_GPIO_PIN=17
# aus 4.2
HOOK_OFFHOOK_LEVEL=1
BUTTON_PINS=sprechen:5,heute:6,kalender:13,rat:19,familie:26,hilfe:21
# aus 4.4, z. B. "USB Audio"
AUDIO_DEVICE_NAME="..."
HANDSET_ALSA_DEVICE=plughw:CARD=handset,DEV=0
SPEAKER_ALSA_DEVICE=plughw:CARD=speaker,DEV=0
CHANNEL=console
# nie ändern auf einem Seniorengerät
ALLOW_CLOUD_LLM=false
```

### 4.6 Funktionstest im Vordergrund
```bash
cd ~/seniorvoice/pipeline
set -a; . ../.env; set +a
python core_service.py --input gpio
```

| # | Aktion | Erwartet |
|---|---|---|
| 1 | Hörer abheben | Signalton und Begrüssung **im Hörer**, nichts im Raum |
| 2 | Etwas fragen | Antwort im Hörer |
| 3 | Auflegen während der Antwort | Antwort bricht ab |
| 4 | Aufgelegt «Heute» drücken | Lautsprecher: «Bitte heben Sie zuerst den Hörer ab …» |
| 5 | Abgehoben «Heute», dann «Kalender» | Datum, Termine, Medikamente bzw. 7 Tage im Hörer |
| 6 | «Sprechen», «Rat» | nichts (noch nicht gebaut, PR 9) |
| 7 | «Hilfe» (Hörer egal) | Lautsprecher: «Ich informiere jetzt Test Tochter. Im Notfall …»; im Log `[console channel] alert` |
| 8 | Testtermin erreicht | Klingeln im Raum; abheben → Ansage im Hörer |
| 9 | Termin klingeln lassen | nach 10 min zweiter Versuch, danach «verpasst» (`appointments_cli.py list`) |
| 10 | «Hilfe» während es klingelt | Klingeln pausiert, Help-Satz ist hörbar, danach klingelt es weiter |
| 11 | Gespräch im Hörer, gleichzeitig Klingeln/Help | im Hörer nur das Gespräch, im Raum nur Klingeln/Help (offener Prüfpunkt aus PR #4) |

Beenden mit Ctrl+C. Gesprächstext steht nie im Log (A8).

### 4.7 Autostart
```bash
sudo cp ~/seniorvoice/deploy/seniorvoice.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now seniorvoice
journalctl -u seniorvoice -f
sudo reboot     # danach Test 1 und 7 wiederholen
```

## 5. Fehlerbehebung

| Symptom | Ursache / Lösung |
|---|---|
| Dienst startet alle paar Sekunden neu, Log «GPIO» | falscher `GPIO_CHIP` oder Benutzer nicht in Gruppe `gpio` (`groups`). Nach 100 Lesefehlern beendet sich der Kern absichtlich. |
| `import lgpio` schlägt fehl | venv ohne `--system-site-packages` erstellt; neu anlegen oder `sudo apt install python3-lgpio`. |
| Knopf löst doppelt oder von selbst aus | Kabel zu lang/ungeschirmt: externer 10-kΩ-Pull-up, `GPIO_DEBOUNCE_MS=50`. |
| Gespräch startet beim Auflegen statt beim Abheben | `HOOK_OFFHOOK_LEVEL` umstellen. |
| `aplay: … Device or resource busy` | PulseAudio/PipeWire hält die Karte (Desktop-Image). Lite-Image verwenden oder für den Benutzer abschalten: `systemctl --user mask pulseaudio.socket pulseaudio.service` bzw. `pipewire.socket pipewire-pulse.socket wireplumber.service`. |
| `aplay: … No such card` | udev-Regel greift nicht (Adapter an anderem Port) → 4.3 wiederholen. |
| Kein Ton, kein Fehler | `HANDSET_ALSA_DEVICE` leer → Standard-Ausgang. Pegel in `alsamixer -c handset` (Mute = `MM`, mit `m` lösen). |
| Dienst startet alle 5 s neu, Log «ValueError» | Kommentar hinter einem Wert in `.env` (siehe 4.5). |
| «No input device matching …» | `AUDIO_DEVICE_NAME` passt nicht; Liste steht in der Fehlermeldung. |
| Beide Adapter heissen gleich, Mikrofon falsch gewählt | Zweiten Adapter eines anderen Modells nehmen. Code-Erweiterung, die das Mikrofon über die udev-Kartennamen wählt, ist vorgeschlagen, aber noch nicht gebaut. |
| `piper: not found` im Dienst | `PATH` in der Service-Datei zeigt nicht auf `.venv/bin` (Benutzer/Pfad angepasst?). |
| Brummen im Lautsprecher | PAM8403 aus eigener 5-V-Quelle oder kürzere Masseleitung; USB-Adapter direkt am Pi statt am Hub. |
| Uhrzeit nach Stromausfall falsch | RTC-Batterie fehlt oder wird nicht geladen (3.7). |

## 6. Am Gerät noch zu klären

- Tatsächliche Pinbelegung, falls von Abschnitt 2 abgewichen wird → `.env`.
- Ob die Hörer-Kapsel ohne Verstärker laut genug ist.
- Namen der beiden Audio-Adapter (eindeutig oder nicht).
- Test 11: keine Vermischung von Hörer und Raumlautsprecher.
