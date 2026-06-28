# SeniorVoice — Präsentations-Kontext für 30–40 Folien
> Exam Presentation · 40 Minuten · ZHAW IoT Data Streaming & Analytics · FS2026  
> Erstellt: 27.06.2026 · Basis: alle Log-Einträge 001–013 + Architekturdokumentation

---

## Hinweis zur Nutzung dieses Dokuments

Jede Folie enthält:
- **Titel** — Folientitel
- **Inhalt** — Kernaussagen / Bullet Points
- **Visuelles Element** — Beschreibung was auf der Folie zu sehen sein soll (Diagramm, Screenshot, Foto, Tabelle, etc.)
- **Sprechtext (ca.)** — Was der Präsentierende ca. sagt (Richtwert: 1 Min. pro Folie)

---

---

## Abschnitt 1: Einleitung (Folien 01–05)

---

### Folie 01 — Titelfolie

**Titel:** SeniorVoice — Lokaler KI-Sprachassistent für ältere Menschen

**Inhalt:**
- Projektname: SeniorVoice
- Kurs: IoT Data Streaming & Analytics (FS2026), ZHAW
- Team: Yanick Fischer (Raspberry Pi 5), Sansone / Haris / Chris (Raspberry Pi 4 / Services)
- Datum: 29.06.2026

**Visuelles Element:**
- Grosse Titelschrift auf dunklem Hintergrund
- Bild: ältere Person mit einem Lautsprecher/Sprachassistenten oder dem Raspberry Pi
- ZHAW-Logo + Kurs-Bezeichnung

**Sprechtext:** "Guten Tag, mein Name ist Yanick Fischer. Ich präsentiere heute SeniorVoice — ein vollständig lokal laufender, datenschutzkonformer KI-Sprachassistent für Menschen ab 65, der auf dem Raspberry Pi 5 betrieben wird. Heute werde ich euch zeigen, wie wir vom ersten Setup bis zur fertigen, demo-reifen Pipeline gekommen sind — inklusive Benchmark-Ergebnissen, Architekturentscheidungen und einem ausblick auf geplante Erweiterungen."

---

### Folie 02 — Team & Projektrollen

**Titel:** Das Team und unsere Rollen

**Inhalt:**
- **Yanick Fischer** — Raspberry Pi 5 (16 GB), MVP-Pipeline, LLM-Benchmarking, Grafana-Dashboard
- **Sansone** — Raspberry Pi 4, Service-Architektur, Kamera-Integration
- **Haris / Chris** — Weitere Microservices, Dokumentation
- Grundidee: Jeder baut seinen eigenen Knoten; gemeinsam ergibt sich ein verteiltes System

**Visuelles Element:**
- Team-Karte mit Namen, Foto oder Icon pro Person
- Kleine Pi-Icons neben jedem Namen zur Kennzeichnung welcher Pi

**Sprechtext:** "Unser Team besteht aus vier Studierenden. Ich war hauptverantwortlich für den Raspberry Pi 5, auf dem die gesamte MVP-Pipeline läuft — von der Spracherkennung bis zur Sprachausgabe. Sansone hat parallel an einem Raspberry Pi 4 gearbeitet und den Kamera-Dienst implementiert. Haris und Chris haben weitere Microservices entwickelt."

---

### Folie 03 — Kurskontext: IoT Data Streaming

**Titel:** Kurskontext: IoT Data Streaming & Analytics

**Inhalt:**
- Kurs: ZHAW, Frühlingssemester 2026
- Thema: Edge-Computing, IoT-Architekturen, Daten-Streaming-Pipelines
- Unsere Interpretation: Ein AI-Edge-Device, das alle Daten lokal verarbeitet — Privatsphäre als Kernfeature
- Abgrenzung zu klassischen Cloud-Assistenten: Alexa, Google Home → alles in der Cloud
- SeniorVoice: **kein einziges Byte Sprache verlässt das Gerät**

**Visuelles Element:**
- Vergleichsgrafik: Links "Cloud-Assistent" (Mikrofon → Cloud → Antwort), rechts "SeniorVoice" (Mikrofon → Pi → Antwort, alles lokal)
- Grüner Haken bei SeniorVoice-Seite: "100% lokal"

**Sprechtext:** "Der Kurs IoT Data Streaming & Analytics befasst sich mit Architekturen, bei denen Daten an der Quelle verarbeitet werden, statt alles in die Cloud zu senden. Wir haben das konsequent umgesetzt: SeniorVoice verarbeitet Sprache vollständig auf dem Raspberry Pi — kein Byte Audiodaten verlässt das Gerät. Das ist der fundamentale Unterschied zu Alexa oder Google Assistant."

---

### Folie 04 — Das Problem: Senioren und Technologie

**Titel:** Das Problem: Warum Senioren Sprachassistenten brauchen — aber keine nutzen

**Inhalt:**
- Menschen 65+: häufigste Barrieren bei Technologienutzung
  - Kleine Schriften / Touchscreens
  - Passwörter, App-Stores, Updates
  - Angst vor Datenmissbrauch ("spioniert mich die Alexa aus?")
- Sprachassistenten könnten helfen — aber: Cloud-Abhängigkeit, fremde Server, unklare Datenpolitik
- Schweiz: Datenschutz besonders sensibles Thema für ältere Generation
- **Gap**: Einfachstes Interface (Sprache) trifft auf grösste Datenschutzbedenken (Cloud-Dienste)

**Visuelles Element:**
- Icon-basierte Aufzählung der Barrieren (kein Touchscreen-Profi, kein Passwort-Manager, etc.)
- Statistik (falls vorhanden): % der 65+ in der Schweiz, die Sprachassistenten nutzen

**Sprechtext:** "Ältere Menschen haben häufig Schwierigkeiten mit modernen digitalen Interfaces. Touchscreens, Passwörter, App-Updates — all das ist für viele eine Barriere. Sprachassistenten wären eigentlich ideal: natürlichstes Interface, keine App nötig. Aber: die grossen Anbieter wie Amazon oder Google senden alle Sprachaufnahmen in ihre Cloud-Server. Für eine Generation, die sehr sensibel auf Datenschutz reagiert, ist das oft ein KO-Kriterium."

---

### Folie 05 — Die Lösung: SeniorVoice

**Titel:** SeniorVoice: Lokaler, privater, seniorengerechter Sprachassistent

**Inhalt:**
- Vollständig lokal auf Raspberry Pi 5 (16 GB RAM, NVMe SSD)
- Kein Internet nötig für normale Nutzung
- Datenschutz: keine Cloud-Übertragung, keine Logs ausserhalb des Geräts
- Seniorengerechte Sprache: Hochdeutsch, kurze Antworten (2–3 Sätze), Siez-Form
- Physische Trigger: PIR-Bewegungssensor (keine App, kein Button)
- Audio-Ausgabe: Bluetooth-Lautsprecher oder (geplant) Telefon-Interface

**Visuelles Element:**
- Produktfoto: Raspberry Pi 5 mit angeschlossenen Geräten (PIR-Sensor, Mikrofon, Lautsprecher)
- Stichwort-Cloud: "Lokal", "Privat", "Einfach", "Deutsch", "Seniorengerecht", "Open Source"

**Sprechtext:** "SeniorVoice ist unsere Antwort auf dieses Problem. Ein Raspberry Pi 5 mit 16 GB RAM, der alle KI-Berechnungen lokal durchführt. Der Sensor erkennt Bewegung, das Mikrofon nimmt die Frage auf, ein lokales Sprachmodell generiert eine Antwort auf Deutsch, und Piper TTS spricht diese aus. Alles auf dem Gerät, ohne Internetverbindung."

---

---

## Abschnitt 2: Projektplanung & Setup (Folien 06–08)

---

### Folie 06 — Projektziele & Meilensteine

**Titel:** Projektziele und Zeitplan (März–Juni 2026)

**Inhalt:**
- Projektzeitraum: März–Juni 2026 (FS2026, ~14 Wochen)
- Meilensteine (chronologisch):
  - W7–W8 (März): Pi Setup, SSH, Docker, Repo, Kamera, NVMe
  - W9 (März): PIR + Sound-Sensor verkabelt, GPIO validiert
  - W11 (Mai): MVP-Pipeline end-to-end ✅
  - W11 (Mai): LLM-Benchmark, Performance-Tuning, Grafana Dashboard ✅
  - W22 (Juni): Präsentationsvorbereitung, Analogtelefon-Konzept ✅

**Visuelles Element:**
- Horizontale Zeitachse (März → Juni) mit Milestone-Markierungen
- Grüne Häkchen für abgeschlossene Meilensteine

**Sprechtext:** "Das Projekt lief über das Frühlingssemester 2026 von März bis Juni. In den ersten Wochen haben wir die Hardware eingerichtet — das ist erstaunlich viel Zeit, da der Pi 5 mit seinem neuen RP1-Chip einige Eigenheiten hat. In der Woche 11 im Mai haben wir dann in wenigen Tagen intensiver Arbeit die gesamte Pipeline zum Laufen gebracht und optimiert."

---

### Folie 07 — Hardware-Setup: Raspberry Pi 5

**Titel:** Hardware: Raspberry Pi 5 als AI-Edge-Device

**Inhalt:**
- **Raspberry Pi 5** (16 GB LPDDR4X RAM, Quad-Core Cortex-A76 @ 2.4 GHz → 2.8 GHz OC)
- **NVMe SSD** (Crucial P310 1TB, via M.2 HAT+ Compact): 444 MB/s Read (5.1× schneller als SD-Karte)
- Headless-Setup: SSH, UFW Firewall, Key-Auth
- **Stromversorgung**: Offizielles Pi 5 Netzteil (5.1V/5A)
- Temperatur unter Last: ~60–65°C, kein Throttling (aktive Kühlung)

**Visuelles Element:**
- Foto des Raspberry Pi 5 mit M.2 HAT, Kühlkörper und Kabelbaum
- Tabelle: "SD-Karte vs. NVMe SSD" mit Read/Write-Speeds

**Sprechtext:** "Das Herzstück ist der Raspberry Pi 5 mit 16 GB RAM — die einzige Konfiguration, die genügend RAM für das lokale Sprachmodell plus alle Pipeline-Komponenten hat. Wir haben früh auf eine NVMe SSD umgestellt: 444 Megabyte pro Sekunde Leserate statt 87 bei der SD-Karte. Das macht vor allem beim Laden des Sprachmodells in den RAM einen messbaren Unterschied."

---

### Folie 08 — Hardware-Übersicht: Alle Komponenten

**Titel:** Hardware-Inventar: Sensoren, Audio, Netzwerk

**Inhalt:**

| Komponente | Funktion | Status |
|---|---|---|
| Logitech C920E Webcam | USB-Mikrofon für STT | ✅ Aktiv |
| Sony SRS-XB23 | Bluetooth-Lautsprecher (A2DP/LDAC) | ✅ Aktiv |
| HC-SR501 PIR-Sensor | Bewegungsauslöser (GPIO4) | ✅ Aktiv |
| Raspberry Pi Camera Module 3 | Bildverarbeitung (nicht aktiv genutzt) | ⬜ Verifiziert |
| HW-496 Sound Sensor | Audio-Trigger (nicht aktiv genutzt) | ⬜ Verifiziert |
| Sense HAT | LED-Display (GPIO-Konflikt mit PIR) | ⬜ Nicht montiert |

**Visuelles Element:**
- Foto: Pi mit allen angeschlossenen Peripheriegeräten, beschriftet
- Alternativ: Blockdiagramm der Hardware-Verbindungen

**Sprechtext:** "Zur Hardware gehören neben dem Pi: ein Logitech C920E Webcam als USB-Mikrofon, ein Sony Bluetooth-Lautsprecher für die Audioausgabe, und ein PIR-Bewegungssensor als Auslöser. Die Kamera und der Sound-Sensor sind eingebaut und verifiziert, aber im MVP nicht aktiv. Das Sense HAT haben wir nicht montiert, weil es GPIO-Pins blockiert, die wir für den PIR-Sensor brauchen."

---

---

## Abschnitt 3: Software-Architektur (Folien 09–13)

---

### Folie 09 — System-Architektur: Die Pipeline

**Titel:** Architektur: Die SeniorVoice MVP-Pipeline

**Inhalt:**
- Monolithische Python-Pipeline (bewusste MVP-Entscheidung)
- Datenfluss: `PIR → Mic → STT → LLM → TTS → Speaker`
- Alle 5 Stufen als separate Python-Module (einfach austauschbar)
- Konfiguration vollständig über Umgebungsvariablen (`config.py`)

**Visuelles Element:**
- Horizontales Flussdiagramm:
  ```
  [HC-SR501 PIR] → [C920E Mic] → [faster-whisper STT]
                                        ↓
  [Sony Speaker] ← [Piper TTS] ← [LLM (Ollama/Kimi)]
  ```
- Jeder Block mit Modul-Name und Technologie

**Sprechtext:** "Die Pipeline folgt einem simplen, linearen Datenfluss. Der PIR-Sensor erkennt Bewegung und triggert die Aufnahme. Das Mikrofon nimmt die Sprache auf, bis zwei Sekunden Stille erkannt werden. Faster-Whisper transkribiert den Ton zu Text. Das Sprachmodell generiert eine Antwort. Piper TTS wandelt den Text in Sprache um. Alles lokal auf dem Pi — kein Cloud-Hop."

---

### Folie 10 — STT: Faster-Whisper

**Titel:** Speech-to-Text: faster-whisper auf ARM64

**Inhalt:**
- **faster-whisper**: CTranslate2-basierte Re-Implementierung von OpenAI Whisper
- Modell: `small` (245 MB), `cpu`-Modus, `int8`-Quantisierung
- Sprache: Deutsch (`de`) — auf Pi 5 ARM64 ohne GPU
- Transkriptionslatenz: ca. 2–4s für 5–10s Sprachaufnahme
- Alternative getestet: `tiny` (schneller, aber schlechtere Schweizerdeutsch-Erkennung)
- Mikrofon: Sounddevice-Library, Silence-Detection via RMS-Threshold (`0.02`)

**Visuelles Element:**
- Blockdiagramm: Mic-Signal → Silence Detection → WAV-Buffer → faster-whisper → Text
- Tabelle: Modell-Vergleich (tiny vs. small: Latenz vs. Qualität)

**Sprechtext:** "Für die Spracherkennung nutzen wir faster-whisper, eine optimierte Variante des OpenAI Whisper-Modells. Das 'small'-Modell mit int8-Quantisierung läuft auf dem ARM64-Prozessor des Pi ohne GPU. Die Transkriptionslatenz liegt bei 2–4 Sekunden — akzeptabel, da wir erst nach Aufnahme-Ende transkribieren. Deutsch-Erkennung ist gut; Schweizerdeutsch wird teilweise auf Hochdeutsch transkribiert, was für unsere Zielgruppe ausreicht."

---

### Folie 11 — LLM-Backend-Architektur

**Titel:** LLM-Backend: Abstraktionsschicht mit Fallback-Chain

**Inhalt:**
- `llm_backend.py`: Abstraktionsschicht über beliebige OpenAI-kompatible Endpunkte
- `LLM_BACKENDS` Env-Var steuert Fallback-Reihenfolge: `"ollama,kimi"` → erst lokal, dann Cloud
- `complete()` — blockierend, für Faktenextraktion
- `stream()` — SSE-Streaming, für per-sentence TTS (Antwort wird gesprochen während LLM noch generiert)
- Fallback nur bei Verbindungsfehler (nicht mid-stream)

**Visuelles Element:**
- Flussdiagramm der Fallback-Chain:
  ```
  Anfrage
     ↓
  [Ollama lokal] → Fehler? → [Kimi Cloud] → Fehler? → RuntimeError
     ↓ (OK)                      ↓ (OK)
  Antwort                      Antwort
  ```

**Sprechtext:** "Das LLM-Backend ist als Abstraktionsschicht implementiert. Via Umgebungsvariable kann ich konfigurieren, welche Backends in welcher Reihenfolge versucht werden sollen. Im Produktionsbetrieb versuchen wir zuerst das lokale Ollama-Modell. Wenn das nicht erreichbar ist, fällt das System automatisch auf die Kimi Cloud-API zurück. Das ermöglicht flexibles Testen ohne Code-Änderungen."

---

### Folie 12 — TTS: Piper und deutsches Voice-Modell

**Titel:** Text-to-Speech: Piper TTS mit deutscher Stimme

**Inhalt:**
- **Piper TTS**: Schnelle, lokale TTS-Engine, optimiert für Embedded-Devices
- Modell: `de_DE-thorsten-medium.onnx` — männliche deutsche Stimme, natürlich klingend
- Latenz: ca. 1–2s für einen Satz (warm)
- Ausgabe: WAV-Datei → PulseAudio → Bluetooth-Lautsprecher
- Wichtige Regel im System-Prompt: **Keine Emojis/Sonderzeichen** (Piper liest sie wörtlich vor: "lächelndes Gesicht")
- Qualitäts-Verbesserung: Streaming-TTS — Pi spricht den ersten Satz, während LLM noch generiert

**Visuelles Element:**
- Waveform-Visualisierung eines synthetisierten Satzes
- Foto: Sony-Lautsprecher mit Bluetooth-Verbindung zum Pi

**Sprechtext:** "Für die Sprachausgabe nutzen wir Piper TTS, ebenfalls lokal auf dem Pi. Das deutsche Modell klingt natürlich und verständlich. Wichtig war eine Regel im System-Prompt: Das Sprachmodell darf keine Emojis oder Sonderzeichen verwenden, weil Piper diese wörtlich vorliest — 'lächelndes Gesicht' statt einem Smiley. Durch per-sentence Streaming beginnt der Pi zu sprechen, während das LLM noch generiert — das verkürzt die wahrgenommene Latenz erheblich."

---

### Folie 13 — Deployment & Konfiguration

**Titel:** Deployment-Workflow und Konfigurationskonzept

**Inhalt:**
- Entwicklung: Mac (VSCode) → `scp` → Raspberry Pi
- Keine Container im MVP (bewusste Entscheidung für Schnelligkeit)
- Konfiguration: **100% via Umgebungsvariablen** (kein Config-File editieren nötig)
- Wichtige Env-Vars: `LLM_API_KEY`, `LLM_BACKENDS`, `LLM_MODEL`, `AUDIO_DEVICE_NAME`
- Start-Varianten:
  ```bash
  python main.py                  # PIR-Trigger, Dauerschleife
  python main.py --no-pir --once  # Keyboard-Trigger, einmalig
  ```

**Visuelles Element:**
- Deployment-Diagramm: Mac → SSH-Tunnel → Pi
- Terminal-Screenshot: `scp`-Befehl, dann `python main.py`-Start

**Sprechtext:** "Der Deployment-Workflow ist bewusst einfach gehalten: ich editiere den Code auf meinem Mac, kopiere die geänderten Dateien via SCP auf den Pi, und starte die Pipeline per SSH. Konfiguration passiert komplett über Umgebungsvariablen — kein editieren von Config-Dateien. Der PIR-Trigger kann durch einen Keyboard-Trigger ersetzt werden, was Tests deutlich einfacher macht."

---

---

## Abschnitt 4: PIR-Sensor & Memory (Folien 14–16)

---

### Folie 14 — PIR-Sensor: Physischer Trigger

**Titel:** PIR HC-SR501: Bewegungserkennung als natürlicher Trigger

**Inhalt:**
- **HC-SR501** PIR-Bewegungssensor
- Anschluss: Signal → GPIO4 (Pin 7), 5V → Pin 2, GND → Pin 6
- Pi 5 Besonderheit: neuer **RP1-Chip** statt BCM-GPIO → erfordert `lgpio` statt `gpiozero`
- Chip-Adressierung: `/dev/gpiochip4` statt `/dev/gpiochip0`
- Kalibrierung: `Sx`-Poti (Empfindlichkeit ~5m), `Tx`-Poti (Hold-Time ~3s), Single-Trigger-Mode
- Nutzer-Experience: Eintreten ins Zimmer → System aktiviert sich → hört zu

**Visuelles Element:**
- Foto: HC-SR501 verdrahtet am Pi GPIO-Header
- Pinout-Diagramm: GPIO4 → Signal, PIN2 → 5V, PIN6 → GND
- Foto: Blick von oben auf den PIR-Sensor und Pi

**Sprechtext:** "Als physischen Auslöser haben wir den HC-SR501 PIR-Bewegungssensor gewählt. Der Sensor erkennt Infrarot-Bewegung und sendet einen Signalpuls an den GPIO-Pin. Der Raspberry Pi 5 hat einen neuen I/O-Controller — den RP1-Chip — der eine andere GPIO-Adressierung verwendet als frühere Pi-Modelle. Das hat uns einige Stunden Debugging gekostet, bis wir herausgefunden haben, dass wir explizit gpiochip4 adressieren müssen."

---

### Folie 15 — Conversation Memory: Session + Langzeit

**Titel:** Memory-System: Session-Gedächtnis + persistente Fakten

**Inhalt:**
- **Session Memory** (In-Memory): Der Agent erinnert sich innerhalb einer Session an den Gesprächsverlauf
  - Timeout: 5 Minuten Inaktivität → Session-Reset
  - Verbaler Reset: "neue Frage", "von vorne", "neues Thema"
  - Max. Turns: konfigurierbar (Standard 10 Paare)
- **Long-Term Memory** (SQLite): Persistente Fakten über den Benutzer
  - Nach jeder Session extrahiert ein LLM-Call Fakten aus dem Verlauf
  - Format: `{category: "name", key: "vorname", value: "Janik"}`
  - Bei nächstem Start werden Fakten in System-Prompt injiziert
  - Beispiel: Agent erinnert sich an Namen und Haustier nach Neustart

**Visuelles Element:**
- Zwei-Layer-Diagramm: Session-Layer (flüchtig) und SQLite-Layer (persistiert)
- Schema der `user_facts`-Tabelle

**Sprechtext:** "SeniorVoice hat zwei Ebenen von Gedächtnis. Das Session-Gedächtnis läuft im RAM und hält den Gesprächskontext innerhalb einer Sitzung. Wenn 5 Minuten lang nichts passiert oder der Nutzer 'neue Frage' sagt, wird es zurückgesetzt. Das Langzeit-Gedächtnis läuft über SQLite: Nach jeder Session extrahiert das Modell Fakten über den Benutzer — Name, Beruf, Haustier — und speichert sie. Bei der nächsten Session werden diese Fakten wieder geladen. Das System erinnert sich also sessionübergreifend an die Person."

---

### Folie 16 — Faktenextraktion & Re-Injection

**Titel:** Technischer Deep-Dive: Zuverlässige Faktenretention

**Inhalt:**
- **Problem**: 1B-Modelle "vergessen" frühe Fakten wenn die Konversation länger wird
- **Lösung 1**: `num_ctx` von 512 auf 2048 erhöhen (mehr Kontext-Fenster)
- **Lösung 2**: Facts Re-Injection — Fakten werden direkt vor jeder User-Nachricht nochmals eingefügt:
  ```
  [Erinnerung — Vorname: Janik, Haustier: Katze Neva]
  
  <User-Nachricht>
  ```
- **Robustheit**: Extraktion in Daemon-Thread (blockiert User nicht), Fallback auf Disk bei Timeout
- Getestete Szenarien: Namensabfrage nach 5 Turns → korrekt; Berufsabfrage → korrekt

**Visuelles Element:**
- Vorher/Nachher: "Test ohne Re-Injection (falscher Beruf)" vs. "Test mit Re-Injection (korrekter Beruf)"
- Code-Snippet: Die Re-Injection-Funktion in `llm_client.py`

**Sprechtext:** "Kleine Sprachmodelle mit 1 Milliarde Parametern haben ein bekanntes Problem: Sie vergessen Informationen aus dem frühen Gesprächsverlauf, wenn die Konversation länger wird. Wir haben zwei Strategien kombiniert: ein grösseres Kontext-Fenster und eine explizite Re-Injection der bekannten Fakten direkt vor jeder Nutzer-Nachricht. Die Kombination dieser beiden Massnahmen macht die Faktenretention über mehrere Turns hinweg zuverlässig."

---

---

## Abschnitt 5: LLM-Entscheidung & Benchmarking (Folien 17–24)

---

### Folie 17 — Die LLM-Frage: Cloud oder Lokal?

**Titel:** Die zentrale Frage: Cloud-LLM oder lokales Modell?

**Inhalt:**
- Ursprüngliche Annahme: Cloud-Modell = höhere Qualität, aber Datenschutz-Problem
- Kimi k2.6 (Moonshot AI Cloud): OpenAI-kompatible API, gutes Deutsch
- Problem: **TTFT (Time To First Token)** bei Kimi: avg. **11.7 Sekunden**, max. 32.7 Sekunden
- Nutzer-Experience: Senioren hören erste Antwort erst nach 11+ Sekunden → zu lang
- Lokale Alternative: Ollama auf dem Pi selbst — höhere Hardware-Anforderungen
- Hypothese: Lokales kleines Modell mit Streaming kann bessere UX liefern

**Visuelles Element:**
- Balkendiagramm: Kimi Cloud TTFT (11.7s) vs. Ziel-TTFT (<2s)
- Annotation: "11 Sekunden Stille = Senior denkt, Gerät ist kaputt"

**Sprechtext:** "Die entscheidende Frage für SeniorVoice: Cloud oder lokal? Cloud-Modelle wie Kimi k2.6 liefern qualitativ gute Antworten — aber die Zeit bis zum ersten Token, die TTFT, war im Schnitt fast 12 Sekunden, mit Spitzen bis zu 32 Sekunden. Für einen Senior, der mit einem Sprachassistenten spricht, ist diese Wartezeit fatal: Nach 12 Sekunden Stille denkt man, das Gerät sei kaputt. Das hat uns motiviert, lokale Modelle ernsthaft zu evaluieren."

---

### Folie 18 — Benchmark-Methodik

**Titel:** Benchmark-Methodik: Systematischer Modellvergleich

**Inhalt:**
- **Tool**: `benchmark_models.py` — eigens entwickeltes CLI-Tool
- **Testset**: 4 deutsche Prompts (Alltagsfragen für Senioren)
- **Metriken**:
  - `tok/s` (Tokens pro Sekunde) — Generierungsgeschwindigkeit
  - `TTFT` (Time To First Token) — subjektiv wahrgenommene Latenz
  - `Cold Start TTFT` vs. `Warm Start TTFT`
- **Protokoll**: 3 Runden × 4 Prompts = 12 Runs pro Modell; Modell zwischen Runs entladen
- **Logging**: Alle Ergebnisse in SQLite + JSON-Export

**Visuelles Element:**
- Screenshot: CLI-Ausgabe von `benchmark_models.py` mit Tabelle
- Diagramm: Was ist TTFT (Zeitachse: Request → First Token → Last Token)

**Sprechtext:** "Für den Vergleich haben wir ein eigenes CLI-Benchmark-Tool entwickelt. Es testet jedes Modell mit vier deutschen Alltagsfragen in drei Runden und misst zwei Kernmetriken: die Tokens pro Sekunde als Masszahl für die Generierungsgeschwindigkeit, und die TTFT — die Zeit bis zum ersten Token, die bestimmt wie lange der Nutzer auf die erste gesprochene Silbe wartet. Alle Ergebnisse werden in SQLite gespeichert und können in Grafana visualisiert werden."

---

### Folie 19 — Getestete Modelle: Übersicht

**Titel:** Getestete Modelle: 9 lokale + 1 Cloud-Baseline

**Inhalt:**
| Modell | Params | Quant | Status |
|---|---|---|---|
| gemma3:4b | 4B | Q4_K_M | Zu langsam (2.5 tok/s) |
| **gemma3:1b** | 1B | Q4_K_M | **Kandidat** |
| llama3.1:8b | 8B | Q4_K_M | Disqualifiziert (<1.5 tok/s + schlechtes Deutsch) |
| mistral:7b | 7B | Q4_K_M | Disqualifiziert (<1.5 tok/s + schlechtes Deutsch) |
| granite4.1:3b | 3B | — | Schlechtes Deutsch |
| gemma3n:e2b | ~2B | — | Unterperformend |
| gemma3n:e4b | ~4B | — | Unterperformend |
| gemma4:e2b | ~2B | — | Thinking-Modell, TTFT 82–175s (!) |
| gemma4:e4b | ~4B | — | Thinking-Modell, TTFT 82–175s (!) |
| liquidai/lfm2.5-350m | 350M | Q8_0 | Disqualifiziert (schlechtes Deutsch) |
| **Kimi k2.6 (Cloud)** | — | — | Referenz: 6 tok/s, 11.7s TTFT |

**Visuelles Element:**
- Tabelle wie oben, farblich hervorgehoben
- Rote Kreuz-Icons bei disqualifizierten Modellen, grünes Häkchen bei Kandidaten

**Sprechtext:** "Wir haben 9 verschiedene lokale Modelle systematisch getestet, plus Kimi Cloud als Referenz. Die 7B und 8B-Modelle waren zu langsam — unter 1.5 Tokens pro Sekunde, ausserdem machten sie auf Deutsch viele Grammatikfehler. Die Gemma4-Modelle sind interessant, aber als sogenannte 'Thinking Models' rechnen sie intern sehr lange bevor sie eine Antwort ausgeben — TTFT von bis zu 175 Sekunden, komplett unusable für einen Voice-Assistant."

---

### Folie 20 — Benchmark-Ergebnis: Der Durchbruch

**Titel:** Key Finding: Thread-Optimierung verdoppelt den Durchsatz

**Inhalt:**
- Ausgangslage (Baseline): gemma3:1b → **3.8 tok/s** (ondemand Governor, 4 Threads)
- Erkenntnis: Pi 5 hat 4 Cortex-A76 Cores
- Bei 4 Inference-Threads bleibt **kein Core** für Ollama-Server, OS-Scheduling, Memory-Controller frei
- Thread-Contention halbiert den Durchsatz!
- Lösung: `num_thread=3` in Ollama Modelfile

| Threads | tok/s | TTFT warm | vs. Baseline |
|---|---|---|---|
| 4 (Default) | 4.8 | 1183ms | +26% |
| 2 | 7.0 | 1003ms | +84% |
| **3** | **8.3** | **914ms** | **+118%** |

**Visuelles Element:**
- Balkendiagramm der drei Thread-Konfigurationen (spektakulärer Unterschied sichtbar)
- Annotation: "Sweet Spot: 3 Threads für 4-Core-CPU"

**Sprechtext:** "Die grösste Entdeckung im gesamten Benchmarking-Prozess war die Thread-Optimierung. Mit 4 Inference-Threads war der Durchsatz paradoxerweise schlechter als mit 3 Threads. Der Grund: Wenn alle 4 Cortex-A76 Kerne mit LLM-Inferenz beschäftigt sind, gibt es keinen freien Kern mehr für den Ollama-Server selbst, das Betriebssystem oder den Memory-Controller. Die Thread-Contention bremst alles. Mit 3 Threads: 8.3 Tokens pro Sekunde, +118% gegenüber der Baseline."

---

### Folie 21 — Overclock: +32% auf 2.8 GHz

**Titel:** Hardware-Tuning: Overclock auf 2.8 GHz (+32% Throughput)

**Inhalt:**
- Pi 5 Standard-Takt: 2.4 GHz (Cortex-A76)
- Getestete Overclock-Stufen:
  - **2.8 GHz** (`arm_freq=2800`, `over_voltage_delta=25000`): +32% tok/s, +24% TTFT
  - **3.0 GHz** (`arm_freq=3000`, `over_voltage_delta=50000`): nur +35% (+3% mehr als 2.8 GHz!)
- Temperatur unter Last: max. 64.8°C, kein Throttling (aktive Kühlung)
- Backup: `config.txt.bak` vor Overclock → schnelles Revert möglich
- **Entscheid**: 2.8 GHz als Produktionseinstellung (bestes Kosten-Nutzen-Verhältnis)

**Visuelles Element:**
- Balkendiagramm: 2.4 GHz vs. 2.8 GHz vs. 3.0 GHz (tok/s)
- Tabelle mit Voltage-Delta und Temperatur pro Stufe
- Annotation: "Doppeltes Voltage für nur 3% Mehrleistung → nicht lohnend"

**Sprechtext:** "Über Overclock können wir den Prozessortakt erhöhen, ohne Softwareänderungen. 2.8 GHz brachten uns 32% mehr Tokens pro Sekunde — mehr als die theoretisch erwarteten 17%, weil der schnellere Speichercontroller ebenfalls profitiert. Den aggressiveren Overclock auf 3.0 GHz haben wir getestet, aber nur 3% Mehrleistung bei doppeltem Spannungsdelta ist das Risiko für ein Dauerbetriebsgerät nicht wert."

---

### Folie 22 — Finales Produktionsmodell: gemma3:1b-prod

**Titel:** Produktionsmodell: gemma3:1b-prod — alle Optimierungen kombiniert

**Inhalt:**
- Alle Optimierungen in einem Ollama-Modelfile kombiniert:
  ```
  FROM gemma3:1b
  PARAMETER num_thread 3
  PARAMETER num_ctx 512
  PARAMETER num_batch 128
  ```
- Auf Pi 5 @ 2.8 GHz OC:

| Metrik | Baseline (Session 008) | gemma3:1b-prod (Session 011) | Delta |
|---|---|---|---|
| tok/s | 3.8 | **10.4** | **+174%** |
| TTFT warm | ~2000ms | **698ms** | **-65%** |
| TTFT cold | ~5000ms | 5138ms | ~= |

**Visuelles Element:**
- Grosse Infografik: "3.8 → 10.4 tok/s" mit +174%-Annotation
- Vorher/Nachher-Karte mit allen drei Optimierungsschritten (Thread, Governor, Overclock)

**Sprechtext:** "Das Produktionsmodell gemma3:1b-prod kombiniert alle Optimierungen: 3 Threads, 512 Token Kontext-Fenster, Batch-Grösse 128, auf einem Prozessor mit Performance-Governor und 2.8 GHz Overclock. Ergebnis: 10.4 Tokens pro Sekunde. Das ist 174% besser als unsere Ausgangsmessung — fast dreimal so schnell. Und die TTFT ist auf 698 Millisekunden gesunken, gegenüber 11.7 Sekunden beim Kimi Cloud-Modell."

---

### Folie 23 — Cloud vs. Lokal: Das Endurteil

**Titel:** Cloud vs. Lokal: Finaler Vergleich für SeniorVoice

**Inhalt:**

| Kriterium | Kimi Cloud (k2.6) | gemma3:1b-prod (lokal) | Gewinner |
|---|---|---|---|
| TTFT | 11.7s avg, 32.7s max | **0.7s** | 🏆 Lokal |
| tok/s | 6.0 | **10.4** | 🏆 Lokal |
| Antwortqualität (Deutsch) | Sehr gut | Gut | ☁️ Cloud |
| Datenschutz | Alle Anfragen zu Moonshot-Servern | 100% lokal | 🏆 Lokal |
| Internetabhängigkeit | Ja | Nein | 🏆 Lokal |
| Kosten | API-Kosten pro Token | Stromkosten (Pi) | 🏆 Lokal |
| **Nutzer-Experience** | **Schlecht (>11s Wartezeit)** | **Gut (<1s bis erstes Wort)** | 🏆 **Lokal** |

**Sprechtext:** "Der direkte Vergleich ist eindeutig: Lokal gewinnt in fast jeder Kategorie. Die Antwortqualität ist beim Cloud-Modell besser — das 1B-Parameter Modell hat weniger Wissen und macht gelegentlich Fehler. Aber für unsere Zielgruppe ist die User-Experience entscheidend: 12 Sekunden Wartezeit sind schlicht inakzeptabel für einen Senioren-Sprachassistenten. Das lokale Modell antwortet in weniger als einer Sekunde mit dem ersten gesprochenen Wort."

---

### Folie 24 — Grafana-Dashboard: Live-Monitoring

**Titel:** Observability: Grafana Dashboard mit SQLite-Datenquelle

**Inhalt:**
- **Grafana 11.6.0** (arm64) auf Pi, Port 3000
- **frser-sqlite-datasource v4.0.2** Plugin — liest direkt aus `seniorvoice.db`
- 5 Dashboard-Panels:
  1. Benchmark tok/s by Model (Barchart)
  2. Benchmark TTFT by Model (Barchart)
  3. Benchmark History tok/s over Time (Timeseries)
  4. Live Interaction Latency STT/LLM/TTS/Total (Timeseries)
  5. Interaction Errors: Total, Fehlerquote (Stat)
- Zugriff via SSH-Tunnel: `ssh -L 3000:localhost:3000 yanick@192.168.1.36`
- Dashboard-JSON versioniert in `docs/grafana/dashboard_import.json`

**Visuelles Element:**
- Screenshot: Grafana-Dashboard mit allen 5 Panels
- Pfeil-Annotation: "SSH-Tunnel → localhost:3000 im Browser"

**Sprechtext:** "Für Monitoring haben wir Grafana auf dem Pi installiert und direkt mit unserer SQLite-Datenbank verbunden. Dort landen alle Benchmark-Ergebnisse und alle Live-Interaktions-Timing-Daten. Das Dashboard zeigt uns sowohl historische Benchmark-Vergleiche als auch die Live-Latenz jedes Pipeline-Schritts in Echtzeit. Ich kann von meinem Mac aus per SSH-Tunnel auf dieses Dashboard zugreifen."

---

---

## Abschnitt 6: Qualität & Seniorengerechte UX (Folien 25–27)

---

### Folie 25 — System-Prompt Engineering für Senioren

**Titel:** System-Prompt: Sprachmodell für Senioren konfigurieren

**Inhalt:**
- System-Prompt definiert das Verhalten des Agenten
- Wichtigste Regeln für SeniorVoice:
  - **Keine Emojis/Sonderzeichen** — Piper liest sie wörtlich vor
  - **Siez-Form** (Sie statt du) — kulturell korrekt für CH Senioren
  - **Kurze Antworten** (2–3 Sätze) — nicht überfordern
  - **Anti-Halluzination**: "Das weiss ich leider nicht" statt erfinden
  - **Begrüssung nur beim ersten Turn** — bei Folgefragen direkte Antwort
  - **Persönliche Fakten korrekt nutzen** — Modell verwechselt sonst User mit sich selbst

**Visuelles Element:**
- Split-Screen: Links "Schlechte Antwort" (mit Emoji, falscher Anrede, halluziniertem Beruf), rechts "Gute Antwort" (korrekt, kurz, Sie-Form)
- Code: `_BASE_SYSTEM_PROMPT` aus `llm_client.py`

**Sprechtext:** "Der System-Prompt ist der Schlüssel zur seniorengerechten Nutzeroberfläche. Wir haben ihn iterativ optimiert, indem wir echte Test-Gespräche geführt und Probleme dokumentiert haben. Drei häufige Probleme: Das Modell verwendet Emojis, die Piper wörtlich vorliest. Es duzt den Nutzer statt Siezen. Und bei kleinen Modellen kommt es zu Halluzinationen — das Modell erfindet Fakten. Explizite Regeln im System-Prompt lösen alle drei Probleme."

---

### Folie 26 — Audio-Feedback: Akustische Rückmeldung

**Titel:** UX-Detail: Audio-Feedback Chimes

**Inhalt:**
- **Problem**: Senioren wissen nicht, ob das Gerät hört — kein visuelles Feedback
- **Lösung**: Zwei akustische Signaltöne
  - `listen_chime`: Aufsteigend C5→E5 (300ms) — spielt NACH Trigger, signalisiert "ich höre zu"
  - `thinking_chime`: Absteigend E5→C5 (260ms) — spielt VOR LLM-Call, signalisiert "ich denke nach"
- Implementierung: numpy Sinuswellen → int16 WAV → PulseAudio
- Keine externen Sound-Dateien nötig — generiert beim ersten Aufruf im Cache
- A2DP-Bluetooth-Latenz: Erster Ton wird manchmal geschluckt (A2DP Wake-Up Latenz ~200ms)

**Visuelles Element:**
- Zeitachse der Interaktion mit Chime-Zeitpunkten markiert
- Wellenform-Visualisierung beider Chimes (ascending vs. descending)

**Sprechtext:** "Ein oft übersehenes UX-Detail: Ältere Menschen brauchen klares Feedback, ob das Gerät gerade hört oder denkt. Wir haben zwei Töne implementiert — ein aufsteigendes Motiv wenn das Gerät anfängt zu hören, und ein absteigendes wenn es verarbeitet. Diese Töne werden über numpy generiert, ohne externe Sound-Dateien. Ein kleines Problem: Bluetooth hat eine eingebaute Wake-Up-Latenz von 200 Millisekunden, die manchmal den ersten Ton schluckt."

---

### Folie 27 — Structured Logging und Interaction-Daten

**Titel:** Observability: Structured Logging und Interaction-Tracking

**Inhalt:**
- Python `logging` mit `RotatingFileHandler` (5 MB × 5 Backups)
- Log-Format: `%(asctime)s [%(name)s] %(levelname)s: %(message)s`
- Alle Timing-Daten in SQLite `interactions`-Tabelle:
  - `stt_duration_ms`, `llm_duration_ms`, `tts_duration_ms`, `total_duration_ms`
  - `trigger_type`, `user_text`, `response_text`, `error`
- Konfigurierbar: `LOG_LEVEL`, `LOG_DIR`, `LOG_MAX_BYTES`, `LOG_BACKUP_COUNT`
- Basis für Grafana-Dashboard (Live Interaction Latency Panel)

**Visuelles Element:**
- Schema der `interactions`-Tabelle
- Screenshot: `pipeline.log`-Datei mit strukturierten Log-Einträgen

**Sprechtext:** "Vom ersten Tag an haben wir auf strukturiertes Logging gesetzt. Jede Interaktion wird in SQLite mit genauen Timing-Daten gespeichert: Wie lange hat die Spracherkennung gedauert, das Sprachmodell, die Sprachausgabe. Diese Daten erscheinen im Grafana-Dashboard und erlauben es uns, Regressionsprobleme sofort zu erkennen — wenn zum Beispiel nach einem Update die LLM-Latenz plötzlich steigt."

---

---

## Abschnitt 7: Technische Entscheide (Folie 28)

---

### Folie 28 — Architecture Decision Record (D-Register)

**Titel:** Key Architecture Decisions (D-Register)

**Inhalt:** Wichtigste Entscheide aus dem D-Register (50+ dokumentiert):

| ID | Entscheid | Begründung |
|---|---|---|
| D-04 | lgpio statt gpiozero | Pi 5 RP1-Chip erfordert gpiochip4 |
| D-06 | Monolith statt Docker (MVP) | Schnellerer Weg zum Prototyp |
| D-13 | SQLite für alle persistenten Daten | Stdlib, NVMe-schnell, Grafana-kompatibel |
| D-20 | `llm_backend.py` Abstraktionsschicht | Zero-breaking-change Backend-Wechsel |
| D-37 | `num_thread=3` als Produktionswert | Thread-Contention bei 4 Threads auf 4-Core-CPU |
| D-40 | 2.8 GHz Overclock | +32% bei moderatem Voltage; 3.0 GHz nur +3% mehr |
| D-48 | Facts Re-Injection vor User-Message | Small Models verlieren frühen Kontext |

**Visuelles Element:**
- Tabelle wie oben (Ausschnitt aus dem D-Register)
- Annotation: "50+ Entscheide dokumentiert in CONTEXT.md"

**Sprechtext:** "Alle Architekturentscheide haben wir in einem sogenannten D-Register dokumentiert — 50 nummerierte Entscheide mit jeweils einer Begründung. Das ist ungemein wertvoll wenn Teammitglieder wechseln oder wenn man Monate später versteht warum etwas so gebaut wurde wie es ist. Einige Beispiele: Warum lgpio statt gpiozero — Pi 5 Eigenheit. Warum 3 Threads statt 4 — Thread-Contention-Erkenntnis. Warum Monolith im MVP — Speed to prototype."

---

---

## Abschnitt 8: Geplante Erweiterung — Analogtelefon (Folien 29–30)

---

### Folie 29 — Vision: Analogtelefon als Interface

**Titel:** Geplante Erweiterung: Analogtelefon als physisches Interface

**Inhalt:**
- **Idee**: Altes Analogtelefon als seniorengerechtes Interface (PIR ersetzt durch Hörer-Abheben)
- **Warum ideal für Senioren**: Vertrauteste Technologie seit Jahrzehnten
  - Hörer abnehmen = Gerät hört zu
  - Hörer auflegen = Gespräch beendet
  - Tastatur für optionale Steuerung (Lautstärke, Reset)
- **Was geplant war**: Vollständige Hardware-Integration mit Arduino und Raspberry Pi
- **Warum nicht umgesetzt**: Keine Zeit + fehlende Hardware-Komponenten (Lötstation, Adapter, Arduino)
- Vollständige technische Anleitung dokumentiert in `docs/how-to_analog-telephone.md`

**Visuelles Element:**
- Foto eines analogen Telefons
- Pfeil-Diagramm: "Hörer abnehmen → GPIO-Trigger → Pipeline startet"
- Schematische Skizze des geplanten Aufbaus

**Sprechtext:** "Einer der letzten geplanten Schritte war die Integration eines analogen Telefons als physisches Interface. Die Idee: Für Senioren ist das Telefon das vertrauteste Kommunikationsgerät — sie wissen intuitiv, dass man den Hörer abnimmt um zu reden und auflegt um das Gespräch zu beenden. Das wäre ein deutlich intuitiveres Interface als ein PIR-Sensor. Wir haben das Konzept vollständig ausgearbeitet und dokumentiert, aber aus Zeitgründen nicht mehr umgesetzt."

---

### Folie 30 — Analogtelefon: Technische Architektur

**Titel:** Analogtelefon-Integration: Technische Architektur

**Inhalt:**
- **Layer 1 — Audio**: Hörermikrofon (RJ9/4P4C) → USB-Soundkarte (C-Media Chip) → Pi STT; Pi TTS → PAM8403 Verstärker → Hörermuschel
- **Layer 2 — Trigger**: Gabel-Schalter (Hook Switch, NC) → GPIO Pi 5 (direkt, kein Arduino nötig)
- **Layer 3 — Steuerung**: 3×4 Tastenfeld + Lautstärke-Potentiometer → Arduino Pro Micro → USB Serial/HID → Pi
- **Lötarbeiten**: Hörerkabel ablöten, USB-Adapter-Stecker anlöten (~2h)
- **Software-Impact**: Neues Modul `telephone_trigger.py`; `main.py` um `TRIGGER_MODE=hook` erweitern

**Visuelles Element:**
- ASCII-Architekturdiagramm aus `how-to_analog-telephone.md`
- Teile-Liste mit Kosten (CHF 20–50 Hardware-Budget)

**Sprechtext:** "Die technische Architektur der Telefonintegration ist in drei Schichten aufgeteilt: Audio läuft über einen USB-Soundkarte, die das Hörermikrofon mit der richtigen Impedanz und Mic-Bias-Spannung betreibt. Der Gabel-Schalter geht direkt an einen GPIO-Pin des Pi — das ist einfacher als der PIR-Sensor. Und das Tastenfeld sowie das Lautstärke-Potentiometer werden über einen Arduino Pro Micro gelesen, der dem Pi als USB-Keyboard erscheint."

---

---

## Abschnitt 9: Microservice-Vision (Folie 31)

---

### Folie 31 — Ziel-Architektur: 5 Microservices

**Titel:** Ziel-Architektur: Docker-Compose Microservices

**Inhalt:**
- MVP = Monolith (bewusst für Speed to Prototype)
- Ziel = 5 FastAPI-Microservices via Docker Compose:
  - `stt-service` — faster-whisper STT
  - `llm-service` — Ollama-Proxy + Fallback
  - `action-service` — Trigger-Erkennung (PIR, Hook-Switch, Keyboard)
  - `tts-service` — Piper TTS
  - `logger-dashboard` — SQLite + Grafana Integration
- Skeletons mit `/health`-Endpoint existieren in `seniorvoice/services/`
- Vorteil: Unabhängige Skalierung, unabhängige Updates, klare Trennung

**Visuelles Element:**
- Microservice-Diagramm mit Docker-Compose-Netzwerk
- Vergleich: Monolith-Block vs. Service-Mesh-Diagramm

**Sprechtext:** "Das aktuelle MVP ist ein Monolith — alle Pipeline-Stufen in einem Python-Prozess. Das war die richtige Entscheidung für die Entwicklungsgeschwindigkeit. Die Zielarchitektur sind 5 eigenständige FastAPI-Microservices, orchestriert via Docker Compose. Skeletons mit /health Endpoint existieren bereits. In einem Folgeprojekt würde man von hier aus weitermachen — Service für Service aus dem Monolith herauslösen."

---

---

## Abschnitt 10: Datenschutz & Reflexion (Folien 32–34)

---

### Folie 32 — Datenschutz: Privacy by Design

**Titel:** Datenschutz: Privacy by Design als Kernarchitekturprinzip

**Inhalt:**
- **Kein Audio** verlässt das Gerät — Sprache wird lokal transkribiert
- **Kein Nutzerprofil** in der Cloud — Fakten lokal in SQLite
- **Kein API-Key-Pflicht** — Pipeline funktioniert ohne Cloud-Account
- Einzige externe Verbindung (optional): Kimi Cloud als Fallback-LLM
- **GDPR-kompatibel**: Alle Daten auf eigenem Hardware
- SQLite-Datenbank lokal auf NVMe SSD — kein Netzwerk-Speicher
- Für Senioren kommunizierbar: "Ihr Gerät lernt Sie kennen — niemand sonst"

**Visuelles Element:**
- "Privacy Shield"-Grafik: Raspberry Pi in der Mitte, Cloud-Symbole aussen mit roten Linien (blockiert)
- Checkboxen: ✅ Lokal ✅ Datenschutz ✅ Offline-fähig

**Sprechtext:** "Datenschutz ist kein Nachgedanke — er ist ein Architekturprinzip. Kein Audiobyte verlässt das Gerät. Alle Nutzerdaten — Name, Gewohnheiten, Gesprächsverlauf — bleiben auf der eigenen Hardware. Das System läuft komplett offline. Das ist gegenüber Alexa oder Google Assistant ein fundamentaler Unterschied, der für ältere Menschen und ihre Angehörigen besonders wichtig ist."

---

### Folie 33 — Herausforderungen & Learnings

**Titel:** Was uns überrascht hat: Herausforderungen und Learnings

**Inhalt:**
1. **Pi 5 RP1-Chip** — gpiochip4-Adressierung undokumentiert; kostet 2h Debugging
2. **LLM-Latenz vs. UX** — 10 tok/s reichen für gute UX; TTFT wichtiger als Gesamtgeschwindigkeit
3. **Thread-Contention** — 4 Threads auf 4-Core-CPU sind schlechter als 3 Threads (nicht intuitiv)
4. **NVMe vs. SD-Karte** — 5× Speedup war erwartet; echter Einfluss auf Modell-Ladezeit war grösser als erwartet
5. **System-Prompt-Iteration** — Braucht viele echte Test-Gespräche; theoretische Prompts decken nicht alle Edge Cases
6. **Bluetooth A2DP Latenz** — ~200ms Wake-Latenz schluckt kurze Töne; kabelgebundener Speaker wäre besser

**Visuelles Element:**
- Nummerierte Liste mit Icons (Überraschungs-Icon, Glühbirne-Icon, etc.)
- Screenshot: `test_pir.py`-Output als Beispiel für Debugging

**Sprechtext:** "Die grösste Überraschung war die Thread-Contention. Dass mehr Threads auf einer 4-Core-CPU langsamer sein können als weniger Threads — das ist nicht intuitiv, aber physikalisch erklärbar: Der Memory-Controller und das OS brauchen auch CPU-Zeit. Die zweitgrösste Erkenntnis: TTFT ist wichtiger als Tokens pro Sekunde. Ein Modell das in 700ms antwortet und dann flüssig streamt, fühlt sich besser an als eines das 11 Sekunden schweigt und dann schnell ist."

---

### Folie 34 — Was wir anders machen würden

**Titel:** Retrospektive: Was wir anders machen würden

**Inhalt:**
1. **Frühere Modell-Evaluation** — Wir haben zu lange auf Cloud-LLM gesetzt, bevor wir lokal getestet haben
2. **Kabelgebundener Speaker** — Bluetooth A2DP Latenz ist ein konstantes Problem; USB-Speaker wäre stabiler
3. **Pi 5 Dokumentation lesen** (RP1, gpiochip4) — hätte 2h Debugging gespart
4. **Integration Tests früher** — PIR + Sprache + TTS End-to-End hätte früher getestet werden können
5. **Analogtelefon von Anfang an** — Als Interface hätte es die Entwicklung von Anfang an motiviert
6. **SQLite WAL-Mode von Anfang an** — Erst spät bei Grafana-Setup entdeckt

**Visuelles Element:**
- "If I could do it again..." Retro-Karte mit Post-It-Stil
- Zwei Spalten: "Was gut war" vs. "Was wir ändern würden"

**Sprechtext:** "In der Retrospektive hätten wir lokale Modelle viel früher ernsthaft evaluiert — wir haben zu lange angenommen, dass Cloud-Qualität unschlagbar ist. Das Ergebnis hat uns eines Besseren belehrt. Und das analoge Telefon hätte als Interface von Anfang an im Scope sein sollen — es hätte uns fokussiert und motiviert, und wäre ein differenzierendes Merkmal gegenüber anderen IoT-Projekten gewesen."

---

---

## Abschnitt 11: Demo & Abschluss (Folien 35–40)

---

### Folie 35 — Live-Demo oder Demo-Video

**Titel:** Demo: SeniorVoice in Aktion

**Inhalt:**
- **Live-Demo** (falls Hardware verfügbar):
  1. Bewegung vor PIR-Sensor → Listen-Chime
  2. Frage stellen: "Wie heisse ich?" (Fakten aus vorheriger Session)
  3. Antwort in Echtzeit gesprochen
  4. Folge-Frage: "Was ist mein Beruf?" — Agent erinnert sich
- **Backup-Video** falls Live-Demo nicht möglich:
  - Demo-Video mit `gemma3:1b` (lokal) — Referenz Session 012
  - Parallel-Demo: Kimi Cloud vs. Lokal (TTFT-Unterschied sichtbar)

**Visuelles Element:**
- Foto/Video des Systems im Betrieb
- Terminal-Output: Pipeline-Logs live sichtbar

**Sprechtext:** "Lassen Sie mich eine kurze Demo zeigen. Ich gehe in den Sensorbereich — Sie hören den Listen-Chime, der signalisiert dass das System hört. Ich stelle eine Frage — und etwa eine Sekunde nach meiner letzten Silbe beginnt der Agent zu antworten. Das ist der Unterschied zu Cloud-Modellen: keine 12 Sekunden warten, sondern sofort."

---

### Folie 36 — Performance-Zusammenfassung

**Titel:** Performance-Übersicht: End-to-End Latenzen

**Inhalt:**
Typische End-to-End-Latenz einer Interaktion (gemma3:1b-prod @ 2.8 GHz):

| Pipeline-Stufe | Latenz | Anteil |
|---|---|---|
| STT (faster-whisper small) | 2–4s | ~40% |
| LLM TTFT | **0.7s** | ~10% |
| LLM Gesamt-Generierung | 4–8s | ~30% |
| TTS (Piper, erster Satz) | 1–2s | ~20% |
| **Wahrgenommene Latenz** | **~3.7s** (bis erstes gesprochenes Wort) | — |

- Hinweis: Wahrgenommene Latenz ≠ technische Latenz dank Streaming-TTS

**Visuelles Element:**
- Horizontale Latenz-Karte (Zeitachse) mit Farbblöcken pro Stage
- "User hört ersten Satz" Marker bei ~3.7s

**Sprechtext:** "Die technische Gesamtlatenz liegt bei 7–14 Sekunden für eine vollständige Antwort. Aber durch das Streaming — der Pi spricht den ersten Satz während er noch den Rest generiert — liegt die wahrgenommene Latenz bei etwa 3.7 Sekunden bis zum ersten gesprochenen Wort. Das ist der relevante Wert für die Nutzerwahrnehmung."

---

### Folie 37 — Projektergebnis: Was wurde erreicht?

**Titel:** Projektergebnis: Was haben wir erreicht?

**Inhalt:**
- ✅ **MVP vollständig**: Trigger → STT → LLM → TTS → Speaker, end-to-end
- ✅ **Vollständig lokal**: Kein Cloud-Zwang, offline-fähig
- ✅ **Seniorengerecht**: Hochdeutsch, Siez-Form, kurze Antworten, Anti-Halluzination
- ✅ **Long-Term Memory**: SQLite-Faktenextraktion, sessionübergreifende Erinnerung
- ✅ **Performance-optimiert**: 10.4 tok/s (+174%), 698ms TTFT
- ✅ **Monitoring**: Grafana Dashboard mit SQLite-Datasource, 5 Panels
- ✅ **50+ Architekturentscheide** dokumentiert
- ✅ **13 Session-Logs** dokumentiert
- ⬜ Analogtelefon (konzeptioniert, nicht implementiert)
- ⬜ Docker Microservices (Skeletons vorhanden, nicht migriert)

**Visuelles Element:**
- Checkboxen-Liste (grün/grau) für alle Punkte
- Kreisdiagramm: Implementiert vs. Geplant (aber dokumentiert)

**Sprechtext:** "Was haben wir erreicht? Die gesamte MVP-Pipeline läuft stabil und demo-reif. Sie ist vollständig lokal, seniorengerecht konfiguriert, mit Long-Term Memory und einem Monitoring-Dashboard ausgestattet. Performance haben wir um 174% verbessert. Zwei Punkte sind konzeptioniert aber nicht implementiert: das Analogtelefon und der Microservice-Split. Beide sind detailliert dokumentiert für ein Folgeprojekt."

---

### Folie 38 — Vergleich: SeniorVoice vs. kommerzielle Lösungen

**Titel:** SeniorVoice vs. kommerzielle Alternativen

**Inhalt:**

| Kriterium | Amazon Echo | Google Home | SeniorVoice |
|---|---|---|---|
| Datenschutz | Cloud-Aufnahmen | Cloud-Aufnahmen | 100% lokal |
| Offline-Betrieb | Nein | Nein | Ja |
| Anpassbar | Begrenzt (Skills) | Begrenzt (Actions) | Vollständig (Open Source) |
| Zielgruppe Senior | Generisch | Generisch | Explizit |
| Schweizer Datenschutz | US-Cloud | US-Cloud | GDPR/DSG-konform |
| Kosten | Abo/Gerät | Abo/Gerät | Einmalig (CHF 150 Hardware) |
| Eigenes LLM möglich | Nein | Nein | Ja |

**Visuelles Element:**
- Vergleichstabelle mit Farb-Coding (rot = Problem, grün = Vorteil)

**Sprechtext:** "Wo steht SeniorVoice gegenüber kommerziellen Lösungen? Amazon Echo und Google Home sind poliert und haben grosse Sprachmodelle hinter sich. Aber beide senden alle Sprachaufnahmen in US-amerikanische Cloud-Server — nicht datenschutzkonform in der Schweiz. SeniorVoice ist vollständig lokal, anpassbar, auf die Zielgruppe zugeschnitten, und einmalig für CHF 150 Hardware beschaffbar."

---

### Folie 39 — Ausblick: Nächste Schritte

**Titel:** Ausblick: Was als Nächstes kommen würde

**Inhalt:**
1. **Analogtelefon** (6h Aufwand, CHF 20–50 Hardware) — `docs/how-to_analog-telephone.md` ist bereit
2. **systemd-Services** — Pipeline und Ollama als Autostart-Services
3. **Microservice-Migration** — STT/LLM/TTS als eigenständige FastAPI-Services
4. **Offline-Wetter/Kalender** — lokale Datenquellen (kein Cloud-API)
5. **Mehrsprachigkeit** — Schweizerdeutsch-Whisper-Feintuning
6. **Grösseres lokales LLM** — Wenn Quantisierung/Hardware verbessert wird (z.B. Pi 5 16GB + LPDDR5)
7. **Community-Verbreitung** — Open-Source-Projekt auf GitHub publizieren

**Visuelles Element:**
- Roadmap-Diagramm mit Prioritäten und geschätztem Aufwand
- GitHub-Logo für Open-Source-Ziel

**Sprechtext:** "Die nächsten Schritte sind klar: Das Analogtelefon steht an erster Stelle — die Anleitung ist fertig, es fehlt nur die Hardware und zwei Tage Aufwand. Dann wären systemd-Services für Autostart wichtig, damit das System ohne SSH-Login startet. Langfristig könnte man SeniorVoice als Open-Source-Projekt publizieren — die Idee eines lokalen, datenschutzkonformen Senioren-Assistenten hat Potenzial über den Kursrahmen hinaus."

---

### Folie 40 — Schlussfolie

**Titel:** Danke — SeniorVoice ist Open Source

**Inhalt:**
- **Zusammenfassung in einem Satz**: SeniorVoice zeigt, dass ein datenschutzkonformer, vollständig lokaler KI-Sprachassistent für Senioren auf einer CHF 150 Hardware-Plattform möglich ist.
- Kernaussage für die Prüfung:
  - 174% Performance-Steigerung durch systematisches Benchmarking
  - TTFT: 11.7s (Cloud) → 0.7s (lokal) — Faktor 17 besser
  - 50+ dokumentierte Architekturentscheide
- **Fragen?**
- Repository: `zhaw-iot-seniorvoice`
- Kontakt: yanick.fischer@gmail.com

**Visuelles Element:**
- Titelgrafik (wie Folie 01) mit "Vielen Dank"
- QR-Code zum Git-Repository (falls öffentlich)
- Kontaktinformationen

**Sprechtext:** "SeniorVoice zeigt, dass ein moderner, datenschutzkonformer AI-Sprachassistent heute auf einer 150-Franken-Plattform möglich ist — ohne Abstriche bei der Nutzerfreundlichkeit für ältere Menschen. Die wichtigsten Erkenntnisse: Lokale Modelle schlagen Cloud-Modelle in der User-Experience, wenn man sie richtig tuned. Systematisches Benchmarking ist unersetzlich. Und gute Dokumentation ist so viel wert wie guter Code. Ich freue mich auf Ihre Fragen."

---

---

## Anhang: Folienliste mit Abschnittszuordnung

| # | Folientitel | Abschnitt | Zeit ca. |
|---|---|---|---|
| 01 | Titelfolie | 1: Einleitung | 1 min |
| 02 | Team & Rollen | 1: Einleitung | 1 min |
| 03 | Kurskontext | 1: Einleitung | 1 min |
| 04 | Das Problem | 1: Einleitung | 1 min |
| 05 | Die Lösung | 1: Einleitung | 1 min |
| 06 | Projektplanung | 2: Setup | 1 min |
| 07 | Raspberry Pi 5 | 2: Setup | 1 min |
| 08 | Hardware-Übersicht | 2: Setup | 1 min |
| 09 | Pipeline-Architektur | 3: Architektur | 1 min |
| 10 | STT | 3: Architektur | 1 min |
| 11 | LLM-Backend | 3: Architektur | 1 min |
| 12 | TTS | 3: Architektur | 1 min |
| 13 | Deployment | 3: Architektur | 1 min |
| 14 | PIR-Sensor | 4: Sensor & Memory | 1 min |
| 15 | Conversation Memory | 4: Sensor & Memory | 1 min |
| 16 | Faktenextraktion | 4: Sensor & Memory | 1 min |
| 17 | Cloud vs. Lokal | 5: LLM & Benchmarks | 1 min |
| 18 | Benchmark-Methodik | 5: LLM & Benchmarks | 1 min |
| 19 | Getestete Modelle | 5: LLM & Benchmarks | 1 min |
| 20 | Thread-Optimierung | 5: LLM & Benchmarks | 1 min |
| 21 | Overclock | 5: LLM & Benchmarks | 1 min |
| 22 | gemma3:1b-prod | 5: LLM & Benchmarks | 1 min |
| 23 | Cloud vs. Lokal Endurteil | 5: LLM & Benchmarks | 1 min |
| 24 | Grafana Dashboard | 5: LLM & Benchmarks | 1 min |
| 25 | System-Prompt | 6: UX Qualität | 1 min |
| 26 | Audio-Feedback | 6: UX Qualität | 1 min |
| 27 | Logging | 6: UX Qualität | 1 min |
| 28 | D-Register | 7: Entscheide | 1 min |
| 29 | Telefon-Vision | 8: Telefon-Erweiterung | 1 min |
| 30 | Telefon-Architektur | 8: Telefon-Erweiterung | 1 min |
| 31 | Microservice-Vision | 9: Zielarchitektur | 1 min |
| 32 | Datenschutz | 10: Reflexion | 1 min |
| 33 | Herausforderungen | 10: Reflexion | 1 min |
| 34 | Retrospektive | 10: Reflexion | 1 min |
| 35 | Demo | 11: Demo & Abschluss | 2 min |
| 36 | Performance-Summary | 11: Demo & Abschluss | 1 min |
| 37 | Projektergebnis | 11: Demo & Abschluss | 1 min |
| 38 | Vergleich Kommerziell | 11: Demo & Abschluss | 1 min |
| 39 | Ausblick | 11: Demo & Abschluss | 1 min |
| 40 | Schlussfolie | 11: Demo & Abschluss | 1 min |
| **Total** | | | **~41 Minuten** |
