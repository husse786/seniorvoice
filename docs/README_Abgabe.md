# SeniorVoice — Abgabe IoT Data Streaming & Analytics FS2026

**Gruppe:** Yanick Fischer · Teammitglied 3 · Teammitglied 1 · Teammitglied 2  
**Betreuer:** Prof. Christian Weber  
**Abgabedatum:** 28. Juni 2026

---

> **Hauptdokumentation (Kurzfassung):** [`Projektdokumentation.md`](Projektdokumentation.md) — konsolidierte Abschlussdokumentation mit Architektur, Benchmark-Ergebnissen, Lessons Learned und Fortführungsideen.
>
> **Detaillierte Arbeitsschritte & Logs:** GitHub → `seniorvoice/docs/logs/` (14 chronologische Log-Einträge, März–Juni 2026) — dokumentiert jeden Entwicklungsschritt inkl. Messwerte, Entscheidungen und Blockers.

---

## Inhalt dieser Abgabe

| Datei / Link | Beschreibung |
|---|---|
| `Projektdokumentation.md` | Vollständige Projektdokumentation (konsolidiert): Projektübersicht, Architektur, Entwicklungsprozess, Benchmark-Ergebnisse, Lessons Learned, Fortführungsideen, Kosten |
| `Präsentation_SeniorVoice.pdf` | Ergebnispräsentation (Folien für die Abschlusspräsentation vom 29.06.2026) |
| GitHub Repository | Vollständiger Quellcode, Konfigurationen, Detail-Logs → siehe unten |

---

## GitHub Repository (öffentlich)

**URL:** [https://github.com/yanickfischer/seniorvoice](https://github.com/yanickfischer/seniorvoice)

Relevante Verzeichnisse im Repository:

| Pfad | Inhalt |
|---|---|
| `seniorvoice/pipeline/` | Gesamter Python-Quellcode der MVP-Pipeline (14 Module) |
| `seniorvoice/docs/logs/raspi5-main-prototyp/` | 14 chronologische Arbeitsprotokolle (März–Juni 2026) |
| `seniorvoice/docs/grafana/dashboard_import.json` | Grafana Dashboard (reproduzierbarer API-Import) |
| `seniorvoice/docs/hardware/Hardware-Beschaffung.pdf` | Vollständige Hardware-Kostenübersicht |
| `seniorvoice/docs/how-to_analog-telephone.md` | Technische Anleitung: Analogtelefon als zukünftiges Interface |
| `seniorvoice/services/` | Microservice-Skeletons (FastAPI, je /health-Endpoint) |
| `CONTEXT.md` | Aktueller Projektstand mit 50 dokumentierten technischen Entscheiden |

---

## Projekt auf einen Blick

SeniorVoice ist ein vollständig lokaler, datenschutzkonformer KI-Sprachassistent auf dem Raspberry Pi 5 für Personen ab 65 Jahren. Keine Cloud, kein Smartphone, kein technisches Vorwissen erforderlich.

```
PIR-Sensor → Mikrofon → faster-whisper STT → Ollama (gemma3:1b) → Piper TTS → BT-Speaker
```

Alle Sprachdaten werden lokal verarbeitet. Interaktionen werden in SQLite geloggt und via Grafana visualisiert.

**Schlüsselresultat Performance-Tuning:** 3.8 tok/s → 10.4 tok/s (+174%) durch Overclock (2.8 GHz) + Thread-Optimierung (num_thread=3).
