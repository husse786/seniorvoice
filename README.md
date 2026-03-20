# SeniorVoice 🎙️
**Lokaler KI-Sprachassistent für ältere Personen**  
ZHAW IoT Data Streaming & Analytics · FS 2026  
Team: Yanick · Chris · Sansone · Haris

---

## Inhaltsverzeichnis

- [Was ist SeniorVoice?](#was-ist-seniorvoice)
- [Für neue Teammitglieder](#für-neue-teammitglieder)
- [Repo-Struktur](#repo-struktur)
- [Mit Claude arbeiten](#mit-claude-arbeiten)

---

## Was ist SeniorVoice?

SeniorVoice ist ein vollständig lokaler, datenschutzkonformer KI-Sprachassistent auf Raspberry Pi. Er hilft älteren Personen (65+) bei digitalisierten Alltagsaufgaben — ohne Smartphone, ohne Cloud, ohne technisches Vorwissen.

### Das Problem

Ältere Menschen sind zunehmend mit digitalen Prozessen konfrontiert (Online-Terminbuchung, Apps, Portale), haben aber weder die Geräte noch die digitale Kompetenz dafür. Bestehende Sprachassistenten wie Alexa oder Siri sind cloudbasiert, datenschutzkritisch und nicht für Senioren konzipiert.

### Die Lösung

Ein eigenständiges Gerät, das auf Bewegung reagiert, auf Deutsch zuhört, versteht und antwortet — vollständig lokal auf dem Raspberry Pi verarbeitet. Keine Daten verlassen das Gerät.

```
PIR-Sensor  ──►  Mikrofon  ──►  STT  ──►  LLM  ──►  TTS  ──►  Lautsprecher
                                 │                     │
                            Transkript             Antwort (DE)
                                 └──────────────────────┘
                                         SQLite + Grafana
```

### Kernprinzipien

- **Privacy by Design** — alle Verarbeitung on-device, kein Cloud-Upload
- **Kein Smartphone nötig** — standalone Gerät, Sprachsteuerung
- **Deutsch** — optimiert für Schweizer Alltagssprache
- **Einfach** — klare, ruhige Antworten für nicht-technikaffine Nutzer

### Tech Stack

| Komponente | Technologie |
|---|---|
| Hardware | Raspberry Pi 5 (16 GB) |
| STT | faster-whisper (small) |
| LLM | Ollama — llama3.2:3b / phi3-mini |
| TTS | Piper TTS (de_DE-thorsten) |
| Services | Python 3.11 + FastAPI + Docker Compose |
| Storage | SQLite |
| Dashboard | Grafana |
| Sensor | PIR HC-SR501 (Wake-Trigger) |

---

## Für neue Teammitglieder

### 1 — Voraussetzungen

- Python 3.11+
- Docker + Docker Compose
- Git
- SSH-Zugang zum Raspberry Pi (Yanick kontaktieren für Key-Setup)

### 2 — Repo klonen

```bash
git clone https://github.com/yanickfischer/seniorvoice.git
cd seniorvoice
```

### 3 — Virtual Environment einrichten

```bash
python3 -m venv .venv
source .venv/bin/activate        # Mac / Linux
# .venv\Scripts\activate         # Windows
```

### 4 — Branching-Strategie

| Branch | Zweck |
|---|---|
| `main` | Stabiler Stand — nur via Pull Request |
| `dev` | Aktiver Entwicklungszweig |
| `feature/[service-name]` | Pro Service / Feature (z.B. `feature/stt-service`) |

```bash
# Neuen Feature-Branch erstellen
git checkout dev
git pull
git checkout -b feature/dein-service
```

### 5 — Commit-Konvention

| Prefix | Wann |
|---|---|
| `feat:` | Neue Funktionalität |
| `fix:` | Bugfix |
| `chore:` | Setup, Konfiguration, Dokumentation |
| `test:` | Tests hinzufügen oder anpassen |
| `refactor:` | Umstrukturierung ohne Funktionsänderung |

Beispiel: `git commit -m "feat: stt-service /transcribe endpoint"`

### 6 — SSH-Zugang zum Raspberry Pi

Der Pi läuft headless auf `192.168.1.36`. Zugang nur via SSH Key-Auth.

Vollständige Anleitung: [`docs/ssh_access_guide.md`](docs/ssh_access_guide.md)

Kurzversion:
```bash
# Key generieren (einmalig)
ssh-keygen -t ed25519 -C "deinname@seniorvoice"

# Public Key an Yanick schicken
cat ~/.ssh/id_ed25519.pub

# Verbinden (nachdem Key hinzugefügt wurde)
ssh deinname@192.168.1.36
```

### 7 — Projektdokumentation

Alle relevanten Dokumente liegen in `docs/`:

| Datei | Inhalt |
|---|---|
| `docs/projektantrag.md` | Vollständiger Projektantrag — Architektur, Scope, Zeitplan |
| `docs/arbeitsprotokoll.md` | Technisches Arbeitsprotokoll — was wurde gemacht, welche Entscheide getroffen |
| `docs/workpackages.md` | Arbeitspakete mit Status — hier sieht man was als nächstes dran ist |
| `docs/prompt_master.md` | Claude-Prompt für jede Coding-Session — lesen bevor du startest |
| `docs/ssh_access_guide.md` | SSH-Einrichtung für Teammitglieder |

### 8 — Nach jeder Session

1. Erledigte Pakete in `docs/workpackages.md` mit ✅ + Datum + Name markieren
2. Protokolleintrag in `docs/arbeitsprotokoll.md` hinzufügen
3. Committen und pushen:

```bash
git add .
git commit -m "feat: [was du gemacht hast]"
git push
```

---

## Repo-Struktur

```
seniorvoice/
├── docs/                        # Projektdokumentation
│   ├── projektantrag.md
│   ├── arbeitsprotokoll.md
│   ├── workpackages.md
│   ├── prompt_master.md
│   └── ssh_access_guide.md
├── services/                    # Microservices
│   ├── stt-service/             # Speech-to-Text (Port 8001)
│   ├── llm-service/             # LLM via Ollama (Port 8002)
│   ├── action-service/          # Intent-Router (Port 8003)
│   ├── tts-service/             # Text-to-Speech (Port 8004)
│   └── logger-dashboard/        # SQLite + Grafana (Port 8005/3000)
├── data/
│   ├── sqlite/                  # SQLite Datenbank (gitignored)
│   └── grafana/                 # Grafana Volumes (gitignored)
├── docker-compose.yml           # Alle Services zusammen
├── .env                         # Config (gitignored — .env.example vorhanden)
└── .venv/                       # Python venv (gitignored)
```

---

## Mit Claude arbeiten (Antigravity IDE)

### Erstmalige Einrichtung

_Falls du noch nie mit Antigravity gearbeitet hast, schau dir das hier an:_
[https://codelabs.developers.google.com/getting-started-google-antigravity#0]

1. **Antigravity herunterladen** — [https://antigravity.google/](https://antigravity.google/)
2. **Repo klonen** — öffne Antigravity, wähle "Clone Repository" (genau gleich wie in VsCode) und gib folgende URL ein:
```
   https://github.com/yanickfischer/seniorvoice
```
3. **Eigenen Branch erstellen** — benenne ihn nach deinem Namen:
```bash
   git checkout dev
   git pull
   git checkout -b dev-[deinname]
   git push -u origin dev-[deinname]
```
   Beispiel: `dev-yanick`, `dev-chris`, `dev-sansone`, `dev-haris`

4. **`.env` einrichten** — kopiere die Beispieldatei und passe sie an:
```bash
   cp .env.example .env
```

5. **Claude-Session starten** — öffne `docs/prompt_master.md`, kopiere den Prompt und füge ihn in das Claude-Chatfenster in Antigravity ein. Claude liest automatisch den Projektkontext und schlägt den nächsten Schritt vor.

### Modellwahl
- **Sonnet 4.6** — für alle Coding-Tasks
- **Opus 4.6** — für Architekturentscheide oder komplexes Debugging
---

*ZHAW FS 2026 · IoT Data Streaming & Analytics · Team SeniorVoice*
