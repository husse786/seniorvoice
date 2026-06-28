# How-To: Analogtelefon als Sprachassistenten-Interface für SeniorVoice (Raspberry Pi 5)

> **Status:** Konzept & Anleitung — nicht umgesetzt im Rahmen des Projekts.  
> **Zielgruppe:** Technisch versierte Maker/Entwickler mit Löterfahrung.  
> **Geschätzter Aufwand:** 1–2 Tage (Hardware-Umbau + Software-Integration)

---

## Motivation

Ein analoges Telefon ist für ältere Menschen (65+) das natürlichste Interface überhaupt: Hörer abnehmen, sprechen, auflegen. Keine App, kein Touchscreen, keine LED-Buttons. Das SeniorVoice-Projekt nutzt im MVP einen Bewegungssensor (PIR) als Trigger und ein USB-Mikrofon für Audio — beides ist für Entwickler intuitiv, nicht aber für Senioren.

Das Analogtelefon als Interface würde bieten:
- **Physischer Trigger**: Hörer abnehmen = SeniorAgent hört zu; auflegen = Session-Ende
- **Vertraute Haptik**: Hörermikrofon + Ohrhörer als natürliches Spracheingabe/ausgabe-Interface
- **Tastenfeld**: Optionale Steuerung (z.B. Ziffer 1 = Neue Session, Ziffer 2 = Lautstärke hoch)
- **Freisprechfunktion**: Eingebauter Lautsprecher und Mikrofon für Hands-free-Betrieb

---

## Systemarchitektur

```
┌─────────────────────────────────────────────────────────────┐
│                    ANALOGTELEFON (geöffnet)                 │
│                                                             │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────┐  │
│  │ Gabel-       │    │ Hörer        │    │ Tastenfeld    │  │
│  │ Schalter     │    │ (RJ9 / 4P4C) │    │ (3×4 Matrix)  │  │
│  │ (Hook SW)    │    │              │    │               │  │
│  └──────┬───────┘    └──────┬───────┘    └───────┬───────┘  │
│         │                  │                    │           │
│         │           ┌──────┴───────┐            │           │
│         │           │ Mikrofon     │            │           │
│         │           │ (Carbon/     │            │           │
│         │           │  Electret)   │            │           │
│         │           │ + Hörer-     │            │           │
│         │           │ muschel      │            │           │
│         │           └──────┬───────┘            │           │
│         │                  │                    │           │
│         │           ┌──────┴──────┐    ┌────────┴──────┐   │
│         │           │ Lautstärke- │    │ Arduino Nano  │   │
│         │           │ Regler      │    │ / Pro Micro   │   │
│         │           │ (Potenti-   │    │ (im Gehäuse)  │   │
│         │           │  ometer)    │    │               │   │
│         │           └──────┬──────┘    └───────┬───────┘   │
└─────────┼──────────────────┼───────────────────┼───────────┘
          │                  │                   │
          ▼                  ▼                   ▼
   GPIO Pi 5          USB-Audio-         USB-Kabel
   (Hook = Trigger)   Adapter            (Seriell)
                       │                   │
                       ▼                   ▼
               Pi Mic-Input          Pi USB-Port
               Pi Audio-Out          (Serial /dev/ttyACM0)
               (über Verstärker
                PAM8403)
```

### Signalfluss SeniorVoice mit Telefon

```
Hörer abnehmen
→ Gabel-Schalter öffnet (GPIO falling edge)
→ Pi erkennt Trigger (ersetzt PIR)
→ Mikrofon im Hörer → USB-Audio-Adapter → Pi STT (faster-whisper)
→ LLM (Ollama gemma3:1b-prod) generiert Antwort
→ Piper TTS → Pi Audio-Out → Verstärker → Hörer-Muschel
→ Hörer auflegen → GPIO rising edge → Session beenden
```

---

## Benötigte Komponenten

### Pflicht (Audio-Grundfunktion)

| Komponente | Beschreibung | Preis ca. |
|---|---|---|
| USB-Audio-Adapter | C-Media CM119A oder CM108 Chip — aktiver ADC/DAC mit Mic-Bias | CHF 5–15 |
| 3.5mm TRRS-Kabel (kurz) | Oder freigekürztes Handset-Kabel zum Anlöten | CHF 2–5 |
| PAM8403 Verstärkermodul | 2×3W, 5V, für Hörer-Muschel (hohe Impedanz) | CHF 3–8 |
| Dupont-Kabel (F-F, F-M) | Für GPIO-Verbindungen | CHF 3–5 |
| Lötstation + Lötzinn | Für Kabelverbindungen innen im Telefon | — |

### Für Tastenfeld + Potentiometer (vollständige Integration)

| Komponente | Beschreibung | Preis ca. |
|---|---|---|
| Arduino Nano oder Pro Micro | Liest Tastentmatrix + Poti; USB Serial zu Pi | CHF 5–15 |
| — | Arduino Pro Micro: direkt USB HID-fähig (kein treiber nötig) | — |
| Widerstandsnetz 4.7kΩ (×7) | Pull-up für Tastentmatrix-Reihen | CHF 1 |
| Schrumpfschlauch | Isolierung an Lötstellen | CHF 2 |
| Isolierband | Zusätzliche Isolation im engen Gehäuse | CHF 1 |

**Gesamtkosten ca.: CHF 20–50** (ohne Telefon und Lötstation)

---

## Schritt 1: Telefon öffnen und analysieren

### 1.1 Öffnen

1. Gerät vom Stromnetz trennen
2. Schrauben unter dem Gerät lösen (oft unter Gummifüssen versteckt)
3. Innenaufbau fotografieren, bevor etwas verändert wird — **alles dokumentieren**
4. Folgende Bauteile identifizieren:
   - Hauptplatine (mit Telefonchip, RJ11-Buchse, Lautsprecher-Treiber)
   - Gabel-Schalter (Hook Switch) — mechanischer Schalter, der beim Auflegen des Hörers gedrückt wird
   - Höreranschluss (meist RJ9 4P4C Buchse am Boden des Handsets oder 4-adriges Kabel)
   - Freisprecher-Lautsprecher und -Mikrofon (falls vorhanden)
   - Tastenfeld (flexible Leitergummimatte mit Metallkontakten oder Membranfolie)
   - Lautstärke-Potentiometer (Drehregler am Gerät)

### 1.2 Gabel-Schalter identifizieren

- Mit Multimeter auf Durchgang testen: **bei aufgelegtem Hörer = geschlossen (normally closed)**; abgehobenem Hörer = offen
- Mindestens 2 Pins vom Schalter mit Dupont-Kabel abgreifen
- Diese Pins werden direkt an GPIO Pi 5 angeschlossen (kein Arduino nötig)

### 1.3 Hörermikrofon und -Muschel

Das Handset ist über ein 4-adriges Kabel (RJ9 / 4P4C) mit der Basisstation verbunden. Die vier Leiter sind typischerweise:

| Draht | Funktion |
|---|---|
| Grün | Mikrofon + (Electret-Bias) |
| Rot | Mikrofon − (GND) |
| Schwarz | Lautsprecher − |
| Gelb | Lautsprecher + |

> **Hinweis:** Farben können je nach Hersteller abweichen — mit Multimeter verifizieren.

Vorgehen:
1. RJ9-Stecker aus Basisstation abziehen
2. Kabelenden freilegen (2cm Isolierung entfernen)
3. Mikrofon-Pins (Grün/Rot) an USB-Audio-Adapter Mic-In anlöten
4. Lautsprecher-Pins (Schwarz/Gelb) an PAM8403-Ausgang anlöten
5. PAM8403 Eingang vom Pi Audio-Out speisen (via 3.5mm Klinke)

---

## Schritt 2: Audio-Integration

### 2.1 USB-Audio-Adapter

**Empfehlung:** USB-Soundkarte mit **C-Media CM119A** oder **CM108** Chip.
- Enthält Mic-Bias Spannung (1.5–2V) für Electret-Mikrofone
- ADC 16-bit, 48kHz — mehr als genug für STT
- Unter Linux sofort als `hw:X,0` erkennbar, kein Treiber nötig
- Preis: CHF 5–10 auf Ali/Amazon

**Anschluss:**
```
Hörermikrofon (2-Draht) → 3.5mm TRRS Stecker anlöten:
  Tip   (L)  → Lautsprecher links (nicht genutzt — kurz an GND)
  Ring1 (R)  → Lautsprecher rechts (nicht genutzt — kurz an GND)
  Ring2 (Mic)→ Mikrofon + (Grün)
  Sleeve(GND)→ Mikrofon − (Rot)
→ TRRS-Stecker in USB-Adapter Kombi-Buchse
```

> **Alternativ:** USB-zu-RJ9-Adapter (fertig konfektioniert) — enthält alles intern, kein Löten nötig. Aber teurer (CHF 25–50) und nicht für alle Telefonmodelle passend.

### 2.2 Lautsprecher (Hörer-Muschel)

Hörer-Muschel hat typisch 8–32 Ω Impedanz. Der Pi-Audioausgang (3.5mm Klinke) liefert zu wenig Strom für direkte Ansteuerung.

**PAM8403 Verstärkermodul:**
```
Pi 3.5mm Audioausgang → PAM8403 L-IN
PAM8403 5V/GND → Pi 5V/GND
PAM8403 L-OUT → Hörer-Muschel (Schwarz/Gelb)
```

Lautstärke: PAM8403 hat integriertes Potentiometer — auf ca. 40% drehen (Hörer direkt am Ohr = empfindlich).

### 2.3 SeniorVoice Konfiguration (Pi-seitig)

```bash
# USB-Audio-Adapter als Mic-Input verifizieren
arecord -l
# Output: card 2: Device [USB Audio Device], device 0: ...

# In config.py / Env-Var:
export AUDIO_DEVICE_NAME="USB Audio"   # Substring-Match für neuen Adapter
```

`audio_capture.py` findet den Adapter automatisch via Substring-Match auf `AUDIO_DEVICE_NAME`.

---

## Schritt 3: Gabel-Schalter als Trigger (ersetzt PIR)

Der Gabel-Schalter ist normally-closed (NC): Beim Auflegen des Hörers ist der Kreis geschlossen, beim Abheben offen.

### Verkabelung

```
Gabel-Schalter Pin A → GPIO Pi 5 (z.B. GPIO17)
Gabel-Schalter Pin B → GND Pi 5
GPIO17 intern via Pull-Up (3.3V) konfigurieren
```

Mit internem Pull-Up:
- Hörer aufgelegt → Schalter geschlossen → GPIO liest LOW (0)
- Hörer abgehoben → Schalter offen → GPIO liest HIGH (1) → **Trigger!**

### Neues Modul `telephone_trigger.py`

```python
"""Telephone hook switch trigger — ersetzt sensor.py für Telefon-Interface."""

import lgpio
from config import PIR_GPIO_CHIP  # wiederverwendet gpiochip4 Config

HOOK_GPIO_PIN = int(os.getenv("HOOK_GPIO_PIN", "17"))

def wait_for_offhook(chip_handle) -> bool:
    """Blockiert bis Hörer abgehoben wird. Returns True wenn off-hook."""
    lgpio.gpio_claim_input(chip_handle, HOOK_GPIO_PIN, lgpio.SET_PULL_UP)
    while True:
        level = lgpio.gpio_read(chip_handle, HOOK_GPIO_PIN)
        if level == 1:  # off-hook: Schalter offen, Pull-Up → HIGH
            return True
        time.sleep(0.05)

def is_onhook(chip_handle) -> bool:
    """True wenn Hörer aufgelegt (Session beenden)."""
    return lgpio.gpio_read(chip_handle, HOOK_GPIO_PIN) == 0
```

In `main.py`: `sensor.wait_for_trigger()` durch `telephone_trigger.wait_for_offhook()` ersetzen; nach jeder Antwort `is_onhook()` prüfen — bei True Session beenden.

---

## Schritt 4: Tastenfeld (Arduino als Intermediär)

Ein analoges Telefon-Tastenfeld ist eine **3×4 Matrix** (Tasten 1–9, *, 0, #) mit 7 Pins:
- 4 Reihen-Pins (R1–R4)
- 3 Spalten-Pins (C1–C3)

### Warum Arduino statt direktem Pi-GPIO?

- Tastenfeld braucht **schnelles Polling** (1–5ms) — Python-GPIO-Polling ist zu langsam für zuverlässige Erkennung
- Arduino kann alle 7 Pins direkt lesen, Pi 5 GPIO ebenfalls, aber Interrupts sind auf Pi in Python komplexer
- Arduino als **USB-HID-Keyboard** sende Tastendrücke als echte Keyboard-Events → Pi liest sie als normale Tastatureingaben — keine Serial-Library nötig

**Arduino Pro Micro als USB-HID-Keyboard (einfachste Lösung):**

```cpp
// Arduino Pro Micro Firmware
#include <Keyboard.h>
#include <Keypad.h>

const byte ROWS = 4, COLS = 3;
char keys[ROWS][COLS] = {
  {'1','2','3'},
  {'4','5','6'},
  {'7','8','9'},
  {'*','0','#'}
};
byte rowPins[4] = {2, 3, 4, 5};
byte colPins[3] = {6, 7, 8};

Keypad keypad = Keypad(makeKeymap(keys), rowPins, colPins, ROWS, COLS);

void setup() { Keyboard.begin(); }

void loop() {
  char key = keypad.getKey();
  if (key) {
    Keyboard.print(key);  // sendet Tastendrucks als USB-Keyboard-Event
    delay(50);
  }
}
```

Pi liest Tastendrücke dann normal via `input()` oder `sys.stdin` — keine Serial-Kommunikation nötig. Der Arduino erscheint als Tastatur-Gerät unter `/dev/input/`.

### Lautstärke-Potentiometer (optional)

Das Telefon-Potentiometer (typisch 10kΩ–50kΩ) kann an einen Arduino-Analogpin gelesen werden:

```cpp
// Zusatz im Arduino-Loop:
int vol = analogRead(A0);  // 0–1023
// Sende als Serial-Kommando an Pi: "VOL:750\n"
Serial.println("VOL:" + String(vol));
```

Pi-seitig ein einfaches Background-Thread in `main.py`:
```python
import serial, subprocess, threading

def volume_listener():
    ser = serial.Serial('/dev/ttyACM0', 9600)
    while True:
        line = ser.readline().decode().strip()
        if line.startswith("VOL:"):
            raw = int(line[4:])
            pct = raw * 100 // 1023
            subprocess.run(["amixer", "set", "Master", f"{pct}%"], capture_output=True)
```

---

## Schritt 5: Freisprecher-Mikrofon und -Lautsprecher (optional)

Falls das Telefon einen integrierten Freisprecher hat:

- **Freisprecher-Mikrofon:** gleicher Signalpfad wie Hörer-Mic (zweiter USB-Audio-Adapter oder Y-Adapter am gleichen Adapter)
- **Freisprecher-Lautsprecher:** oft 8Ω / 0.5W — ein zweiter PAM8403-Kanal reicht
- Umschaltlogik: Hook-Schalter bestimmt ob Hörer oder Freisprecher aktiv ist; mit `AUDIO_DEVICE_NAME` Env-Var umschaltbar

---

## Schritt 6: SeniorVoice Pipeline-Anpassungen

### `config.py`

```python
# Neuer Env-Var für Telefon-Trigger
HOOK_GPIO_PIN = int(os.getenv("HOOK_GPIO_PIN", "17"))
TRIGGER_MODE = os.getenv("TRIGGER_MODE", "pir")  # "pir" | "hook" | "keyboard"
```

### `main.py` — Trigger-Auswahl

```python
from config import TRIGGER_MODE, HOOK_GPIO_CHIP, HOOK_GPIO_PIN

if TRIGGER_MODE == "hook":
    from telephone_trigger import wait_for_offhook, is_onhook
    trigger_fn = lambda handle: wait_for_offhook(handle)
    stop_fn = lambda handle: is_onhook(handle)
elif TRIGGER_MODE == "pir":
    from sensor import wait_for_trigger
    trigger_fn = wait_for_trigger
    stop_fn = lambda _: False
```

### Starten mit Telefon-Interface

```bash
export TRIGGER_MODE=hook
export HOOK_GPIO_PIN=17
export AUDIO_DEVICE_NAME="USB Audio"
python main.py
```

---

## Risiken & Mitigation

| Risiko | Mitigation |
|---|---|
| Hörermikrofon ist Carbon-Typ (nicht Electret) | Carbon-Mics funktionieren NICHT mit Electret-Bias. Test mit Multimeter: Electret ~1.5V zwischen + und − bei angeschlossenem USB-Adapter. Falls 0V → Carbon-Typ → Mic ersetzen oder Kondensator-Kopplung nötig |
| Hörer-Impedanz zu hoch für PAM8403 | PAM8403 arbeitet ab 4Ω; Telefon-Hörer oft 32–150Ω. Ggf. Ausgangsimpedanz anpassen (Widerstand in Serie) |
| Tastenfeld-Pins nicht zugänglich (SMD-Folie) | Mit Lupe/Mikroskop Kontaktpads auf Folienleiterplatte suchen; Magnet-Draht anlöten |
| USB-Audio-Adapter wird vom Pi nicht erkannt | `dmesg | grep usb` — suche nach `C-Media` oder ähnlichem. Falls kein Treffer: Adapter defekt oder inkompatibles Chip-Modell |
| Lautstärke zu laut/leise im Hörer | PAM8403 Trim-Poti justieren; alternativ `amixer set Master XX%` in Software |

---

## Zeitplan (geschätzte Dauer)

| Schritt | Dauer | Wer |
|---|---|---|
| Telefon öffnen + dokumentieren | 30 min | Hardware-Person |
| Gabel-Schalter testen + GPIO verdrahten | 30 min | Hardware-Person |
| Hörer-Kabel freilegen + Impedanz messen | 45 min | Hardware-Person |
| USB-Audio + PAM8403 anlöten + testen | 1h | Hardware-Person |
| Arduino Firmware schreiben + flashen | 45 min | Software-Person |
| Arduino Tastenfeld-Test + USB-HID bestätigen | 30 min | Software-Person |
| `telephone_trigger.py` schreiben | 30 min | Software-Person |
| `main.py` Trigger-Mode erweitern | 30 min | Software-Person |
| Integrations-Test (End-to-End) | 1h | Beide |
| **Total** | **~6h** | |

---

## Quellen & Referenzprojekte

- [Raspberry Pi Dial Telephone (CrazyRobMiles)](https://github.com/CrazyRobMiles/RaspberryPi-DialTelephone) — Pi im Wählscheiben-Telefon
- [Retro Rotary Phone mit AIY + ChatGPT](https://aallan.medium.com/a-retro-rotary-phone-powered-by-aiy-projects-and-the-raspberry-pi-e516b3ff1528) — Aiasdair Allan, Medium
- [ChatGPT Rotary Phone Hotline (XDA Developers)](https://www.xda-developers.com/take-chatgpt-retro-raspberry-pi-powered-rotary-phone-hotline/) — aktuelles Projekt 2024/2025
- [Matrix Keypad with Arduino (Adafruit)](https://learn.adafruit.com/matrix-keypad?view=all) — vollständige Keypad-Tutorial
- [4x3 Membrane Keypad with Arduino (ElectroPeak)](https://electropeak.com/learn/interfacing-4x3-membrane-matrix-keypad-with-arduino/) — Schritt-für-Schritt
- [TRRS Mic Wiring Guide (AllAboutCircuits)](https://forum.allaboutcircuits.com/threads/wiring-a-3pin-electret-microphone-to-a-trrs-audio-jack.178545/)
- [Raspberry Pi Phone Forum Thread](https://forums.raspberrypi.com/viewtopic.php?t=196910) — Community-Diskussion Hookswitch + Audio
