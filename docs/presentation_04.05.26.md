# SeniorVoice — Status-Praesentation 04.05.2026

**Modul:** IoT Data Streaming & Analytics, ZHAW FS 2026
**Team:** Yanick, Chris, Sansone, Haris | **Betreuer:** Christian Weber
**Projektwoche:** W11

---

## 1 — Projektidee (2-3 Min)

### Problem

- Aeltere Personen (65+) sind zunehmend mit digitalisierten Alltagsprozessen konfrontiert
- Arzttermine, Behoerden, Dienstleistungen: oft nur noch online/per App buchbar
- Bestehende Sprachassistenten (Alexa, Siri, Google) sind **cloudbasiert** und **nicht auf Senioren ausgelegt**
- Abhaengigkeit von Angehoerigen fuer digitale Alltagsaufgaben waechst → soziale Isolation

### Unsere Loesung: SeniorVoice

- **Vollstaendig lokaler** KI-Sprachassistent auf Raspberry Pi 5
- Kein Smartphone, kein Cloud-Upload, kein technisches Vorwissen noetig
- Privacy by Design: alle Daten bleiben auf dem Geraet
- Natuerliche Sprachinteraktion auf Deutsch — warmherzig, geduldig, kurze Antworten

### Kernkonzept

```
Person tritt vor Geraet
   → PIR-Sensor erkennt Bewegung
   → Mikrofon nimmt Sprache auf
   → Sprache wird lokal transkribiert (STT)
   → KI versteht und antwortet (LLM)
   → Antwort wird vorgelesen (TTS)
   → Lautsprecher gibt Antwort aus
```

---

## 2 — Was wurde gemacht? (3-4 Min)

### Hardware-Setup

| Komponente | Status | Details |
|---|---|---|
| Raspberry Pi 5 (16 GB) | Laeuft | Headless, SSH, NVMe-SSD Boot (444 MB/s) |
| NVMe SSD (Crucial P310 1TB) | Laeuft | 5.1x Speedup gegenueber SD-Karte |
| Logitech C920E Webcam | Laeuft | USB-Mikrofon fuer Spracheingabe |
| Sony SRS-XB23 Speaker | Laeuft | Bluetooth 5.0, A2DP, LDAC Codec |
| PIR HC-SR501 | Laeuft | GPIO4, kalibriert — erkennt Personen im Raum |

### Software-Pipeline (MVP — End-to-End funktional)

| Schritt | Technologie | Beschreibung |
|---|---|---|
| Audio-Aufnahme | sounddevice + numpy | Silence-Detection (RMS), stoppt nach 2s Stille |
| Speech-to-Text | faster-whisper (small, int8) | Lokale Transkription, Deutsch, laeuft auf CPU |
| Sprachmodell (LLM) | Moonshot Kimi API (k2.6) | Cloud-API (MVP); Ollama-Fallback vorbereitet |
| Text-to-Speech | Piper TTS (thorsten-medium) | Lokale Sprachsynthese, deutsche Stimme |
| Sensor-Trigger | lgpio (GPIO4) | PIR-Sensor als Hardware-Trigger |

### Architekturentscheid

- **Monolithische Python-Pipeline** statt Docker-Microservices fuer den MVP
- Grund: weniger Moving Parts, schnellerer Weg zum funktionierenden Prototyp
- Microservice-Skeletons existieren bereits in `services/` — Split nach Validierung

### Zusaetzliche Features (ueber MVP hinaus)

- **Session Memory**: Multi-Turn-Konversation mit 5-Minuten-Timeout
- **Long-Term Memory**: SQLite-basiert — Assistent merkt sich Fakten ueber Benutzer
- **Audio-Feedback**: Aufsteigende/absteigende Chimes signalisieren "hoere zu" / "denke nach"
- **Structured Logging**: Python logging mit Rotation (5 MB x 5 Backups)
- **Interaction Logs**: Jede Interaktion mit STT/LLM/TTS-Timing in SQLite → Grafana-ready

### Meilensteine (chronologisch)

| Datum | Was |
|---|---|
| 19.-20.03 | Pi 5 headless Setup, SSH, Docker, NVMe-Migration |
| 25.03 | Kamera, Sense HAT, NVMe-SSD (5.1x read speedup) |
| 28.03 | PIR + Sound-Sensor verdrahtet, GPIO validiert |
| 01.05 | **MVP End-to-End**: Mic → STT → LLM → TTS → Speaker |
| 01.05 | PIR-Sensor kalibriert und in Pipeline integriert |
| 01.05 | Session Memory + Long-Term Memory (SQLite) |
| 02.05 | Kimi k2.6, Audio-Feedback, Structured Logging |

---

## 3 — Live-Demo (3-5 Min)

### Setup

- Pi 5 mit angeschlossenem USB-Mikrofon (C920E) und BT-Speaker (Sony SRS-XB23)
- Terminal via SSH sichtbar auf Beamer/Bildschirm
- PIR-Sensor oder Keyboard-Trigger (`--no-pir` Flag)

### Demo-Ablauf

**Schritt 1 — System starten**
```bash
cd ~/seniorvoice/pipeline
source ../.venv/bin/activate
export LLM_API_KEY=<key>
python main.py --no-pir --once
```
→ System meldet "Bereit" im Terminal

**Schritt 2 — Interaktion ausfuehren**
- ENTER druecken (Keyboard-Trigger) → Listen-Chime ertoeht
- Frage stellen, z.B.: _"Welcher Monat ist der waermste in der Schweiz?"_
- Stille-Erkennung stoppt Aufnahme automatisch
- Thinking-Chime → LLM verarbeitet
- Antwort wird ueber Lautsprecher vorgelesen

**Schritt 3 — Memory demonstrieren (optional, 2. Durchlauf)**
```bash
python main.py --no-pir
```
- Erste Interaktion: _"Ich heisse Yanick und studiere an der ZHAW."_
- Zweite Interaktion: _"Wie heisse ich?"_
- → Assistent erinnert sich (Long-Term Memory)

### Fallback-Plan

- Falls WLAN/API-Probleme: vorab aufgenommenes Video der Demo zeigen
- Falls BT-Speaker-Probleme: `--no-pir` + Terminal-Output zeigen (Text statt Audio)
- Falls Pi nicht verfuegbar: Screenshots + Architekturdiagramm erklaeren

---

## 4 — Ausblick / Naechste Schritte (1 Min)

| Prioritaet | Was | Status |
|---|---|---|
| 1 | Lokales LLM via Ollama (kein Cloud-Abhaengigkeit) | Vorbereitet, noch nicht getestet |
| 2 | systemd-Service (Autostart beim Boot) | Ausstehend |
| 3 | Docker-Compose + Microservice-Split | Skeletons vorhanden |
| 4 | Grafana Dashboard (SQLite-Daten bereits vorhanden) | Ausstehend |

### Offener Punkt

- Kimi K2 Serie wird am **25.05.2026 eingestellt** — Migration auf lokales Ollama-Modell geplant
- Code ist bereits Ollama-ready (gleiche OpenAI-kompatible API)

---

## Zusammenfassung fuer Folie / Einzeiler

> **SeniorVoice** ist ein vollstaendig lokaler KI-Sprachassistent auf Raspberry Pi 5,
> der aelteren Personen auf Deutsch bei Alltagsfragen hilft —
> ohne Cloud, ohne Smartphone, ohne technisches Vorwissen.
> Die MVP-Pipeline (Mikrofon → STT → LLM → TTS → Lautsprecher) laeuft end-to-end,
> inklusive Bewegungserkennung, Gespraechsgedaechtnis und Audio-Feedback.
