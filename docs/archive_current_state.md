# SeniorVoice — Current State

> **Regel:** Diese Datei wird am Ende jeder Session überschrieben — immer nur der aktuelle Stand, kein Verlauf.  
> Verlauf → `logs/` | Alle Aufgaben → `docs/workpackages.md`

---

## Stand: 20.03.2026 · W05 · Yanick

### Wo stehen wir?
W05 Infrastruktur-Setup ist abgeschlossen. Raspberry Pi 5 läuft headless, gehärtet und SSH-zugänglich. Docker und Ollama sind installiert. GitHub Repo ist aufgesetzt mit vollständiger Dokumentationsstruktur (`docs/`, `logs/`). `dev` Branch existiert.

### Nächster Schritt
**A-02** — `docker-compose.yml` Skeleton für alle 5 Services erstellen (in Bearbeitung)

### Danach
**A-03** — Branching-Strategie dokumentieren (bereits umgesetzt, nur noch dokumentieren)  
**A-04** — `llama3.2:3b` auf Pi pullen und Antwortzeit messen

### Offene Blocker
- **A-05** — SSH-Keys von Sansone, Haris, Chris noch ausstehend
- **A-06** — Externer SSH via Uni IoT-Netz — Prof. Weber kontaktieren

### Letzter Log-Eintrag
[001_log_20032026.md](../logs/001_log_20032026.md) — Pi Setup, Security Hardening & Repo Setup
