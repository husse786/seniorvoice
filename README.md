# SeniorVoice
**Lokaler KI-Sprachassistent für ältere Personen**
ZHAW IoT Data Streaming & Analytics · FS 2026
Team: Yanick · Chris · Sansone · Haris

[![SeniorVoice Präsentation](docs/SeniorVoice_TitleImage.png)](docs/SeniorVoice_Local_AI_for_Seniors.pdf)
> Klick auf das Bild öffnet die Zwischenstand-Präsentation (W11, 04.05.2026)

---

## Inhaltsverzeichnis

- [Was ist SeniorVoice?](#was-ist-seniorvoice)
- [Aktueller Stand](#aktueller-stand)
- [Hardware](#hardware)
- [Für neue Teammitglieder](#für-neue-teammitglieder)
- [Repo-Struktur](#repo-struktur)

---

## Was ist SeniorVoice?

SeniorVoice ist ein vollständig lokaler, datenschutzkonformer KI-Sprachassistent auf Raspberry Pi 5. Er hilft älteren Personen (65+) bei Alltagsfragen — ohne Smartphone, ohne Cloud, ohne technisches Vorwissen.

### Das Problem

Ältere Menschen sind zunehmend mit digitalen Prozessen konfrontiert (Online-Terminbuchung, Apps, Portale), haben aber weder die Geräte noch die digitale Kompetenz dafür. Bestehende Sprachassistenten wie Alexa oder Siri sind cloudbasiert, datenschutzkritisch und nicht für Senioren konzipiert.

### Die Lösung

Ein eigenständiges Gerät, das auf Bewegung reagiert, auf Deutsch zuhört, versteht und antwortet — vollständig lokal auf dem Raspberry Pi verarbeitet. Keine Daten verlassen das Gerät.

```
PIR-Sensor → Mikrofon → STT → LLM → TTS → Lautsprecher
                         │              │
                    Transkript      Antwort (DE)
                         └──────────────┘
                           SQLite + Grafana
```

### Kernprinzipien

- **Privacy by Design** — alle Verarbeitung on-device, kein Cloud-Upload
- **Kein Smartphone nötig** — standalone Gerät, Sprachsteuerung
- **Deutsch** — optimiert für Hochdeutsch, warmherziger Ton
- **Einfach** — klare, ruhige Antworten für nicht-technikaffine Nutzer

---

## Aktueller Stand

> **W11 (03.05.2026)** — MVP-Pipeline end-to-end funktional auf Raspberry Pi 5

### Zwischenpräsentation

[SeniorVoice_Local_AI_for_Seniors.pdf](docs/SeniorVoice_Local_AI_for_Seniors.pdf) — Statusbericht W11 (04.05.2026)

### Pipeline (funktional)

```
PIR-Sensor (HC-SR501) → C920E Mikrofon → faster-whisper STT → Ollama LLM → Piper TTS → Sony BT-Speaker
```

### Tech Stack

| Komponente | Technologie | Details |
|---|---|---|
| Hardware | Raspberry Pi 5 (16 GB) | NVMe SSD (Crucial P310), headless |
| STT | faster-whisper (small, int8) | Lokale Transkription, CPU-only |
| LLM (lokal) | Ollama — gemma3:1b | 3.8 tok/s, 1.3s TTFT, Q4_K_M |
| LLM (Cloud-Fallback) | Moonshot Kimi k2.6 | 6.0 tok/s, aber 11.7s TTFT |
| TTS | Piper TTS (de_DE-thorsten-medium) | Lokale Sprachsynthese |
| Audio | PulseAudio | USB-Mic → BT-Speaker Routing |
| Sensor | PIR HC-SR501 (GPIO4) | Bewegungserkennung als Trigger |
| Storage | SQLite (WAL mode) | Long-Term Memory + Interaction Logs |
| Python | 3.13 | venv mit --system-site-packages |

### LLM-Benchmark (12 Modelle getestet)

Vollständige Ergebnisse: [model_comparisson.md](docs/models/model_comparisson.md)

| Model | Type | tok/s | TTFT | German | Status |
|---|---|---|---|---|---|
| gemma3:1b | Local | 3.8 | 1.3s | Acceptable | **Kandidat** |
| gemma3n:e2b | Local | 2.4 | 2.3s | Good | Kandidat |
| kimi-k2.6 | Cloud | 6.0 | 11.7s | Excellent | Zu langsam (TTFT) |
| gemma3:4b | Local | 1.7 | 2.5s | Excellent | Zu langsam |

**Erkenntnis:** gemma3:1b liefert mit Streaming die beste User Experience (~4s bis erstes gesprochenes Wort), obwohl Kimi höhere tok/s hat (11.7s Wartezeit bis erste Antwort).

### Features (über MVP hinaus)

- **Streaming + per-sentence TTS** — Antwort wird satzweise vorgelesen während LLM weiter generiert
- **Session Memory** — Multi-Turn-Konversation mit 5-Minuten-Timeout
- **Long-Term Memory** — SQLite-basiert, merkt sich Fakten über Benutzer
- **Audio-Feedback** — Chimes signalisieren "höre zu" / "denke nach"
- **LLM-Fallback-Chain** — Ollama → Kimi, konfigurierbar via Env-Vars
- **Structured Logging** — RotatingFileHandler (5 MB × 5 Backups)
- **Interaction Logs** — Timing-Daten (STT/LLM/TTS) in SQLite, Grafana-ready

### Nächste Schritte

1. Performance-Tuning gemma3:1b (`num_ctx`-Reduktion, Thread-Count, System-Prompt)
2. Ollama als systemd-Service (Autostart, Model Pre-Load)
3. Pipeline als systemd-Service (Autostart beim Boot)
4. Grafana Performance Dashboard
5. Docker-Compose + Microservice-Split

---

## Hardware

> Vollständige Kostenzusammenfassung und alle Rechnungsdetails: [docs/hardware/Hardware-Beschaffung.pdf](docs/hardware/Hardware-Beschaffung.pdf)

### Benötigte Komponenten (Prototyp-Nachbau)

| Menge | Artikel | Preis CHF |
|------:|---------|----------:|
| 1 | HutoPi Raspberry Pi 5 Starter Kit – 16 GB | 249.00 |
| 1 | Raspberry Pi Official Fan/Heat Sink for Pi 5 | 9.50 |
| 1 | Raspberry Pi Official M.2 HAT+ Compact | 15.70 |
| 1 | Crucial P310 PCIe 4.0 NVMe 2230 M.2 SSD 1 TB | 132.98 |
| 1 | KKSB Gehäuse für Raspberry Pi 5 + HATs, Alu, schwarz | 16.31 |
| 1 | Raspberry Pi Infrarot Bewegungsmelder PIR HC-SR501 | 1.94 |
| 1 | Jumperkabel Dupont Set (60 Stk., für GPIO-Verdrahtung) | ~15.00 |
| | **Summe Beschaffung (ohne bereits vorhandene Geräte)** | **~440 CHF** |

**Bereits vorhanden (nicht beschafft, kein Kostenanteil):**
- Logitech C920E Webcam — als USB-Mikrofon verwendet
- Sony SRS-XB23 Bluetooth-Lautsprecher — als Audioausgabe verwendet

### Hinweis zur Reproduzierbarkeit

Der Prototyp läuft vollständig headless auf dem Raspberry Pi 5 (NVMe-SSD-Boot, PulseAudio, Python 3.13 venv). Für einen Nachbau werden kein Bildschirm und keine Tastatur benötigt — SSH-Zugang genügt. Der PIR-Sensor (HC-SR501) ist über GPIO17 (Pin 11) angeschlossen; alternativ kann `--no-pir` als Startoption genutzt werden, um Keyboard-Triggering zu aktivieren.

---

## Für neue Teammitglieder

### 1 — Voraussetzungen

- Python 3.13+
- Git
- SSH-Zugang zum Raspberry Pi (Yanick kontaktieren für Key-Setup)

### 2 — Repo klonen

```bash
git clone https://github.com/yanickfischer/seniorvoice.git
cd seniorvoice
```

### 3 — Branching-Strategie

| Branch | Zweck |
|---|---|
| `main` | Stabiler Stand — nur via Pull Request |
| `dev` | Aktiver Entwicklungszweig |
| `feature/[name]` | Pro Feature (z.B. `feature/stt-service`) |

```bash
git checkout dev
git pull
git checkout -b feature/dein-feature
```

### 4 — Commit-Konvention

| Prefix | Wann |
|---|---|
| `feat:` | Neue Funktionalität |
| `fix:` | Bugfix |
| `chore:` | Setup, Konfiguration, Dokumentation |
| `test:` | Tests hinzufügen oder anpassen |
| `refactor:` | Umstrukturierung ohne Funktionsänderung |

### 5 — SSH-Zugang zum Raspberry Pi

Der Pi läuft headless auf `192.168.1.36`. Zugang nur via SSH Key-Auth.

```bash
# Key generieren (einmalig)
ssh-keygen -t ed25519 -C "deinname@seniorvoice"

# Public Key an Yanick schicken
cat ~/.ssh/id_ed25519.pub

# Verbinden (nachdem Key hinzugefügt wurde)
ssh deinname@192.168.1.36
```

### 6 — Deploy-Workflow

Code wird auf Mac/PC editiert und via `scp` auf den Pi deployed:

```bash
# Mac → Pi (geänderte Dateien)
scp pipeline/datei.py yanick@192.168.1.36:/tmp/

# Pi (deployen + starten)
sudo cp /tmp/*.py /home/admin/seniorvoice/pipeline/
cd ~/seniorvoice/pipeline
source ../.venv/bin/activate
export LLM_API_KEY=<key>
python main.py --no-pir --once
```

### 7 — Projektdokumentation

| Datei | Inhalt |
|---|---|
| `CONTEXT.md` (Root) | Aktueller Projektstand, Hardware, nächste Schritte |
| `CLAUDE.md` (Root) | Architektur-Regeln, Coding-Konventionen |
| `docs/projektantrag.md` | Vollständiger Projektantrag (Scope, Timeline) |
| `docs/logs/` | Chronologische Arbeitsprotokolle pro Session |
| `docs/models/model_comparisson.md` | LLM-Benchmark-Ergebnisse |
| `docs/hardware/` | Datenblätter aller Hardwarekomponenten (PDF) |

---

## Repo-Struktur

```
seniorvoice/
├── pipeline/                    # MVP Code (aktiv, end-to-end funktional)
│   ├── main.py                  # Orchestrator
│   ├── audio_capture.py         # Mic-Aufnahme + Silence-Detection
│   ├── stt.py                   # faster-whisper Transkription
│   ├── llm_client.py            # Chat-Interface (streaming + non-streaming)
│   ├── llm_backend.py           # LLM-Abstraktionsschicht (Fallback-Chain)
│   ├── tts.py                   # Piper TTS + Playback
│   ├── memory.py                # Long-Term Memory (SQLite)
│   ├── sensor.py                # PIR GPIO4
│   ├── sounds.py                # Audio-Feedback Chimes
│   ├── config.py                # Env-Var Konfiguration
│   ├── logging_config.py        # Structured Logging
│   ├── interaction_log.py       # SQLite Interaction Logger
│   ├── benchmark_models.py      # LLM-Benchmark CLI-Tool
│   └── requirements.txt
├── services/                    # Microservice-Skeletons (inaktiv)
│   ├── stt-service/
│   ├── llm-service/
│   ├── action-service/
│   ├── tts-service/
│   └── logger-dashboard/
├── docs/
│   ├── models/                  # Benchmark-Ergebnisse + JSON-Rohdaten
│   ├── logs/                    # Arbeitsprotokolle pro Session
│   ├── hardware/                # Datenblätter (PDF)
│   └── projektantrag.md         # Projektantrag
├── CONTEXT.md                   # Aktueller Projektstand
└── CLAUDE.md                    # Coding-Regeln für Claude Code
```

---

*ZHAW FS 2026 · IoT Data Streaming & Analytics · Team SeniorVoice*
