# SeniorVoice — Projektdokumentation (Kurzfassung)

**Lokaler KI-Sprachassistent für ältere Personen**

IoT Data Streaming & Analytics · ZHAW FS 2026  
Team: Yanick Fischer (Projektleitung) · Teammitglied 1 · Teammitglied 2 · Teammitglied 3  
Betreuer: Prof. Christian Weber  
Abgabedatum: 28. Juni 2026

---

> **Hinweis zur Dokumentation:** Dieses Dokument ist eine konsolidierte Zusammenfassung des Projekts. Die detaillierten Arbeitsprotokolle (14 Log-Einträge, chronologisch von März bis Juni 2026) sind im öffentlichen GitHub-Repository einsehbar:
>
> **GitHub:** [https://github.com/yanickfischer/seniorvoice](https://github.com/yanickfischer/seniorvoice)  
> **Detail-Logs:** `seniorvoice/docs/logs/raspi5-main-prototyp/`

---

## Inhaltsverzeichnis

1. [Projektübersicht](#1-projektübersicht)
2. [Systemarchitektur](#2-systemarchitektur)
3. [Entwicklungsprozess](#3-entwicklungsprozess)
4. [Technische Ergebnisse](#4-technische-ergebnisse)
5. [Monitoring & Observability](#5-monitoring--observability)
6. [Lessons Learned](#6-lessons-learned)
7. [Ideen zur Fortführung](#7-ideen-zur-fortführung)
8. [Projektkosten und Hardware](#8-projektkosten-und-hardware)
9. [Fazit](#9-fazit)
10. [Links und Ressourcen](#10-links-und-ressourcen)

---

## 1. Projektübersicht

### Problemstellung und Motivation

Ältere Personen — insbesondere ab 65 Jahren — sind zunehmend mit digitalisierten Alltagsprozessen konfrontiert, für die sie weder die geeigneten Geräte noch ausreichend digitale Kompetenz besitzen. Gleichzeitig werden analoge Zugangswege wie telefonische Terminvergabe und Schalterdienstleistungen systematisch abgebaut. Arzttermine und Dienstleistungen werden immer häufiger ausschliesslich online oder über Apps buchbar.

Bestehende Sprachassistenten wie Amazon Alexa, Apple Siri oder Google Assistant sind cloudbasiert, datenschutzkritisch und nicht auf die Bedürfnisse von Seniorinnen und Senioren ausgerichtet. Sie erfordern entweder ein Smartphone als primäres Interface oder senden sensible Sprachdaten an externe Server — beides stellt für ältere Personen eine technische und datenschutzbezogene Barriere dar.

Eine weitere Herausforderung betrifft Menschen im Anfangsstadium von Alzheimer, die teilweise vergessen, welche Medikamente sie täglich einnehmen müssen. Die Abhängigkeit von Angehörigen für digitale Alltagsaufgaben wächst und fördert soziale Isolation.

### Projektidee

SeniorVoice ist ein vollständig lokaler, datenschutzkonformer KI-Sprachassistent auf dem Raspberry Pi 5, der älteren Personen bei digitalen Alltagsaufgaben hilft — ohne Smartphone, ohne Cloud, ohne technisches Vorwissen. Das Gerät reagiert auf Bewegung (PIR-Sensor), hört zu (Mikrofon), versteht Deutsch (lokales Whisper-STT), verarbeitet die Anfrage mit einem lokalen Sprachmodell (Ollama LLM) und antwortet per Lautsprecher (Piper TTS). Alle Interaktionen werden lokal in SQLite gespeichert und in einem Grafana-Dashboard visualisiert.

**Privacy by Design** ist ein nicht verhandelbares Designprinzip: Alle Verarbeitung findet ausnahmslos auf dem Gerät statt. Es verlassen keine Audiodaten, keine Transkripte und keine persönlichen Informationen das lokale Netz.

### Kernziele

| Ziel | Ergebnis |
|---|---|
| End-to-End Sprachverarbeitung lokal | ✅ Erreicht |
| Deutsche Spracherkennung und Antwort | ✅ Erreicht |
| Alle Daten lokal — kein Datenabfluss | ✅ Erreicht |
| Interaktionen in SQLite geloggt | ✅ Erreicht |
| Grafana-Dashboard für Monitoring | ✅ Erreicht |
| Microservices in Docker Compose | ⚠️ Skeletons vorhanden, monolithische Pipeline für MVP gewählt |

---

## 2. Systemarchitektur

### Finale Pipeline-Architektur (MVP)

Der ursprüngliche Projektantrag sah fünf FastAPI-Microservices in Docker Compose vor. Im Verlauf der Entwicklung wurde ein entscheidender Architekturentscheid getroffen (D-06): Für den MVP wurde eine **monolithische Python-Pipeline** gewählt, um schneller zu einem funktionsfähigen Prototyp zu gelangen. Die Microservice-Skeletons existieren im Verzeichnis `seniorvoice/services/` als Basis für eine spätere Migration.

Die finale MVP-Pipeline:

```
PIR-Sensor (HC-SR501) → C920E Mikrofon → faster-whisper STT → Ollama (gemma3:1b-prod) → Piper TTS → Sony BT-Speaker
```

### Pipeline-Komponenten

| Modul | Datei | Technologie | Funktion |
|---|---|---|---|
| Orchestrator | `main.py` | Python 3.13 | Ablaufsteuerung, PIR/Keyboard-Trigger |
| Audio-Aufnahme | `audio_capture.py` | sounddevice, numpy | Mic-Aufnahme, RMS-basierte Silence-Detection |
| Speech-to-Text | `stt.py` | faster-whisper (small, cpu, int8) | Sprache → Transkript (Deutsch) |
| LLM-Client | `llm_client.py` | OpenAI-kompatibles API | Chat-Interface, Session History, Facts Re-Injection |
| LLM-Backend | `llm_backend.py` | Ollama + Kimi Fallback | Abstraktionsschicht, Streaming, Fallback-Chain |
| Text-to-Speech | `tts.py` | Piper TTS (de_DE-thorsten-medium) | Text → Sprache, Playback via PulseAudio |
| PIR-Sensor | `sensor.py` | lgpio, GPIO4, gpiochip4 | Bewegungserkennung als Wake-Trigger |
| Langzeitgedächtnis | `memory.py` | SQLite (WAL-Mode), LLM-Faktenextraktion | Persistente Nutzerinfo über Sessions hinweg |
| Interaction-Logger | `interaction_log.py` | SQLite | Timing-Daten (STT/LLM/TTS/Total) pro Interaktion |
| Benchmark-CLI | `benchmark_models.py` | SQLite, JSON-Export | Systematischer Modellvergleich |
| Audio-Feedback | `sounds.py` | numpy | Chime-Töne bei Listen/Thinking (keine externen Dateien) |
| Logging | `logging_config.py` | Python RotatingFileHandler | Strukturiertes Logging (5 MB, 5 Backups) |
| Konfiguration | `config.py` | Umgebungsvariablen | Alle Einstellungen via Env-Vars |

### Hardware-Übersicht

| Komponente | Spezifikation | Status im MVP |
|---|---|---|
| Raspberry Pi 5 (16 GB) | arm64, 4× Cortex-A76 @ 2.8 GHz (OC) | ✅ Aktiv — Hauptrechner |
| NVMe SSD Crucial P310 1 TB | M.2 HAT+ Compact, 444 MB/s Read | ✅ Aktiv — Boot-Device |
| Logitech C920E Webcam | USB Audio `hw:2,0`, Analog Stereo Input | ✅ Aktiv — Mikrofon |
| Sony SRS-XB23 | Bluetooth 5.0, A2DP Sink, Codec LDAC | ✅ Aktiv — Lautsprecher |
| PIR HC-SR501 | GPIO4, PIN2 (5V), PIN6 (GND) | ✅ Aktiv — Wake-Trigger |
| Raspberry Pi Camera Module 3 (IMX708) | 4608×2592, CSI | ✅ Verifiziert — im MVP nicht genutzt |
| Sound Sensor HW-496 | GPIO27 | ✅ Verifiziert — im MVP nicht genutzt |
| Sense HAT v2 | Temperatur, Luftfeuchtigkeit, LEDs | ⚠️ GPIO-Konflikt mit PIR — nicht montiert |

---

## 3. Entwicklungsprozess

### W01–W05: Konzeption und Hardware-Beschaffung (März 2026)

In den ersten Wochen wurden Projektidee, Architekturkonzept und Hardwareevaluation abgeschlossen. Der Projektantrag definierte fünf FastAPI-Microservices in Docker Compose sowie eine klare Privacy-by-Design-Strategie.

### W05 (19.–20. März 2026): Pi 5 Setup und Infrastruktur

Der Raspberry Pi 5 (16 GB) wurde headless mit Raspberry Pi OS aufgesetzt (Log 001). Das System wurde umfassend gehärtet: UFW aktiviert, Docker UFW-Bypass deaktiviert (`iptables: false`), SSH-Key-Auth eingerichtet, Root-Login gesperrt. Docker Engine 29.3.0 und Ollama 0.18.2 wurden vorinstalliert.

### W03 (25. März 2026): NVMe-SSD-Migration

In Log 003 wurde das System von der MicroSD-Karte auf die NVMe-SSD migriert. Der Performance-Gewinn war erheblich: Read-Geschwindigkeit von 87.7 MB/s auf 444.2 MB/s (+407 %, 5.1× schneller), Write von 63.2 MB/s auf 210.0 MB/s (+232 %). Gleichzeitig wurden Kamera (IMX708), Sense HAT und GPIO-Port-Doubler verifiziert — der Doubler erwies sich als inkompatibel mit dem KKSB-Aluminiumgehäuse, womit der PIR-Sensor als alleiniger Wake-Trigger festgelegt wurde.

### W05 (28. März 2026): Sensoren und GPIO

Log 004 dokumentierte die vollständige Verdrahtung von PIR-Sensor (HC-SR501) und Sound-Sensor (HW-496). Die GPIO-Adressierung erforderte lgpio statt gpiozero, da der Pi 5 den RP1-Chip mit gpiochip4 verwendet — ein wichtiger Unterschied zum Pi 4.

Parallel dazu startete ein Teammitglied mit dem Raspberry Pi 4 (2 GB RAM): Setup mit Raspberry Pi OS, Docker Engine, Tailscale VPN und OpenClaw (Log raspi4-testing-device/001). OpenClaw wurde später wieder entfernt und durch direkte API-Calls ersetzt.

### W11 (1. Mai 2026): MVP End-to-End — erster lauffähiger Prototyp

**Meilenstein:** Die erste lauffähige MVP-Pipeline wurde in Log 005 dokumentiert. Der entscheidende Architekturentscheid: monolithische Python-Pipeline statt Docker-Microservices, um schneller zu einem funktionierenden Prototyp zu kommen.

Hardware-Integration: Logitech C920E per USB als Mikrofon, Sony SRS-XB23 per Bluetooth als Lautsprecher, PulseAudio als Audio-Routing-Schicht. Python-Umgebung mit sounddevice, faster-whisper und Piper TTS.

Erster erfolgreicher End-to-End-Test:
- Frage: „Welcher Monat ist der Wärmste in der Schweiz?"
- STT: Korrekt transkribiert (100% Konfidenz, Sprache: `de`)
- LLM: „Der Juli ist in der Regel der wärmste Monat in der Schweiz."
- TTS: Korrekt synthetisiert und über BT-Lautsprecher abgespielt

### W11 (1. Mai 2026): PIR-Sensor und Langzeitgedächtnis

Log 006 dokumentierte die vollständige PIR-Sensor-Integration (GPIO4, kalibriert mit Delay-Regler und Empfindlichkeit). Log 007 ergänzte Session Memory (In-Memory mit 5-Minuten-Timeout für natürliche Multi-Turn-Gespräche) und Long-Term Memory (SQLite-basiert, LLM-gestützte Faktenextraktion in Daemon-Thread).

### W11 (2. Mai 2026): Logging-Infrastruktur und LLM-Backend

Log 008 ergänzte die Pipeline um strukturiertes Python-Logging (RotatingFileHandler, 5 MB, 5 Backups) und SQLite Interaction Logging mit Timing-Daten pro Interaktion (STT-Latenz, LLM-Latenz, TTS-Latenz, Total). Audio-Feedback-Töne wurden via numpy generiert (keine externen Sound-Dateien nötig).

Log 009 führte `llm_backend.py` als LLM-Abstraktionsschicht ein: Eine Fallback-Chain (Ollama → Kimi Cloud) via Env-Var `LLM_BACKENDS`, SSE-Streaming, per-sentence TTS (Piper spricht schon während LLM noch generiert), sowie das Benchmark-CLI-Tool `benchmark_models.py`.

### W11 (3. Mai 2026): LLM-Benchmark — 9 Modelle im Vergleich

Log 010 dokumentierte den systematischen Benchmark aller verfügbaren LLM-Modelle. Neun lokale Ollama-Modelle und die Kimi k2.6 Cloud-API wurden mit identischem Test-Setup bewertet: 4 deutsche Prompts × 3 Runden = 12 Runs pro Modell.

**Ergebnis:** gemma3:1b wurde als primärer lokaler Kandidat identifiziert. Mit 3.8 tok/s und 1.3s TTFT liefert es durch Streaming eine bessere User Experience als Kimi Cloud (TTFT durchschnittlich 11.7s, Maximum 32.7s). Die gemma4-Familie wurde als „Thinking Models" disqualifiziert (82–175s TTFT auch warm — für Voice-Assistenten unbenutzbar).

### W11 (3. Mai 2026): Performance-Tuning — +174% Durchsatz

Log 011 dokumentierte eine mehrstufige Performance-Tuning-Session:

**CPU Governor:** Umstellung von `ondemand` auf `performance` (alle 4 Cores fix @ 2.4 GHz) brachte +24% Throughput (3.8 → 4.7 tok/s). Persistiert via systemd oneshot-Unit.

**Thread-Optimierung:** Der grösste Hebel war die Entdeckung, dass `num_thread=3` den Throughput gegenüber dem Standard (4 Threads) verdoppelt. Ursache: Bei 4 Inference-Threads auf 4 Cortex-A76-Cores bleibt kein Core für den Ollama-Server, das Betriebssystem und den Memory-Controller frei — Thread-Contention bremst massiv.

**Overclock:** 2.8 GHz (`arm_freq=2800`, `over_voltage_delta=25000`) brachte +32% gegenüber Stock-Frequenz. 3.0 GHz lieferte nur +3% mehr bei doppeltem Voltage-Delta — nicht lohnend für ein Dauerbetriebsgerät.

**Grafana Dashboard:** Grafana 11.6.0 (arm64) wurde installiert und mit dem frser-sqlite-datasource Plugin v4.0.2 an die SQLite-Datenbank angebunden. Das Dashboard "SeniorVoice Performance" zeigt 5 Panels: Benchmark tok/s, Benchmark TTFT, Benchmark History over Time, Live Interaction Latency und Interaction Errors. Zugriff via SSH-Tunnel (`ssh -L 3000:localhost:3000`).

### W11 (3. Mai 2026): Demo-Vorbereitung und System-Prompt-Tuning

Log 012 dokumentierte die finalen Anpassungen für die Live-Demo:
- Kritischer Bug behoben: Faktenextraktion wurde bei Ollama-Backend stillschweigend übersprungen (falscher API-Key-Guard)
- System-Prompt überarbeitet: Keine Emojis (Piper TTS liest sie wörtlich vor), konsequente Sie-Form, Anti-Halluzination-Regel
- Facts Re-Injection implementiert: Bekannte Nutzerfakten werden vor jeder User-Nachricht erneut eingefügt (Defense-in-Depth gegen Kontextverlust bei kleinen Modellen)
- LLM-Warmup beim Pipeline-Start: Eliminiert Cold-Start-Latenz (Ollama lädt Modell nach 5 Min. aus RAM)
- Context-Window auf 2048 Tokens erhöht: 512 Tokens reichen nicht für System-Prompt + Fakten + History

### W22 (27. Juni 2026): Analogtelefon-Konzept

Als letzter Hardware-Erweiterungsschritt wurde in Log 013 das Konzept eines analogen Telefons als physische Benutzeroberfläche dokumentiert. Ein Analogtelefon hätte Webcam und Bluetooth-Lautsprecher ersetzt und wäre besonders seniorengerecht: ein vertrautes Gerät mit klarer Bedienlogik (Hörer abnehmen = sprechen). Das Konzept wurde vollständig in `docs/how-to_analog-telephone.md` dokumentiert, konnte aber aus Zeit- und Hardwaregründen nicht implementiert werden.

### W23 (28. Juni 2026): Hardware-Dokumentation und Projektabschluss

Log 014 dokumentierte die vollständige Hardware-Beschaffungsübersicht (`docs/hardware/Hardware-Beschaffung.md` und `.pdf`) mit Gesamtkosten von CHF 895.42, kategorisiert nach Verwendung. Das README.md wurde mit einer Hardware-Sektion für Nachbauer ergänzt.

---

## 4. Technische Ergebnisse

### LLM-Benchmark: 9 lokale Modelle + Kimi Cloud

Alle Modelle wurden mit 4 deutschen Prompts × 3 Runden (12 Runs) auf dem Raspberry Pi 5 (arm64) bewertet.

| Modell | Grösse | tok/s (warm) | TTFT warm | TTFT cold | Deutsche Qualität |
|---|---|---|---|---|---|
| gemma3:1b (stock) | 815 MB | 3.8 | 1300ms | 4938ms | Gut |
| gemma3:4b | ~2.5 GB | 2.4–1.7 | ~2000ms | ~8000ms | Sehr gut |
| llama3.1:8b | ~4.5 GB | <1.5 | >3000ms | — | Schlecht (Grammatikfehler) |
| mistral:7b | ~4.1 GB | <1.5 | >3000ms | — | Schlecht |
| granite4.1:3b | ~2 GB | — | — | — | Getestet |
| gemma3n:e2b | — | — | — | — | Getestet |
| gemma3n:e4b | — | — | — | — | Getestet |
| gemma4:e2b | — | 82–175s TTFT | 82–175s | — | Disqualifiziert (Thinking Model) |
| gemma4:e4b | — | 82–175s TTFT | 82–175s | — | Disqualifiziert (Thinking Model) |
| liquidai/lfm2.5-350m | 379 MB | 4.6 | 1178ms | 1524ms | Unbrauchbar (inkohärent) |
| **Kimi k2.6 (Cloud)** | — | 6.0 | **11.7s avg** | — | Sehr gut — aber zu langsam |

**Kernfinding:** gemma3:1b mit Streaming (per-sentence TTS) liefert eine bessere User Experience als Kimi Cloud, obwohl die rohe Qualität geringer ist: 4 Sekunden bis zum ersten gesprochenen Wort gegenüber über 11 Sekunden bei Kimi Cloud.

### Performance-Tuning: +174% Durchsatz

Ausgehend von der Baseline (gemma3:1b stock, 4 Threads, 2.4 GHz, `ondemand`-Governor):

| Konfiguration | Clock | Threads | tok/s | TTFT warm | vs. Baseline |
|---|---|---|---|---|---|
| Baseline (02.05) | 2.4 GHz | 4 (Default) | 3.8 | 1300ms | — |
| + Performance Governor | 2.4 GHz | 4 | 4.7–4.8 | 1073ms | +26% |
| + num_thread=2 | 2.4 GHz | 2 | 7.0 | 1003ms | +84% |
| + num_thread=3 | 2.4 GHz | 3 | 8.3 | 914ms | **+118%** |
| gemma3:1b-prod | 2.4 GHz | 3 | 8.1 | 915ms | +113% |
| **gemma3:1b-prod (OC 2.8 GHz)** | **2.8 GHz** | **3** | **10.4** | **698ms** | **+174%** |
| gemma3:1b-prod (OC 3.0 GHz) | 3.0 GHz | 3 | 10.7 | 664ms | +182% |

**Entscheid:** 2.8 GHz als Produktionseinstellung — +174% Gewinn bei moderatem Voltage-Delta (25000). 3.0 GHz bringt nur +3% mehr bei doppeltem Voltage, was für ein Dauerbetriebsgerät nicht lohnenswert ist.

### Finale Produktionskonfiguration

```
Modell:    gemma3:1b-prod (Ollama Modelfile)
           FROM gemma3:1b
           PARAMETER num_thread 3
           PARAMETER num_ctx 512–2048 (Produktionswert: 2048)
           PARAMETER num_batch 128

Hardware:  Raspberry Pi 5 @ 2.8 GHz (arm_freq=2800, over_voltage_delta=25000)
           CPU Governor: performance (alle 4 Cores fix)

Leistung:  10.4 tok/s (warm), 698ms TTFT (warm)
           Temperatur unter Last: max 64.8°C, kein Throttling (0x0)
```

---

## 5. Monitoring & Observability

### SQLite als einheitliche Datenschicht

Alle Laufzeitdaten werden lokal in einer einzigen SQLite-Datenbank (`~/seniorvoice/seniorvoice.db`, WAL-Mode) gespeichert. Diese Entscheidung (D-13, D-19, D-30) vereinfachte die Grafana-Integration erheblich — eine Datenquelle für alle Panels.

| Tabelle | Inhalt |
|---|---|
| `user_facts` | Persistente Nutzerfakten (category/key/value, Upsert-Logik, `active`-Flag) |
| `interactions` | Jede Interaktion mit STT/LLM/TTS/Total-Latenz-Daten und Fehler-Flag |
| `benchmark_results` | Einzelne Benchmark-Runs (tok/s, TTFT, token_count, response_text, is_cold_start) |
| `benchmark_aggregates` | Modell-aggregierte Benchmark-Kennzahlen pro Session |

### Grafana Dashboard "SeniorVoice Performance"

Grafana 11.6.0 (arm64) läuft als systemd-Service auf Port 3000 und ist via SSH-Tunnel zugänglich (`ssh -L 3000:localhost:3000 yanick@<PI_IP>`). Das Dashboard zeigt fünf Panels:

| Panel | Typ | Datenquelle |
|---|---|---|
| Benchmark tok/s by Model | Barchart | `benchmark_aggregates` |
| Benchmark TTFT by Model | Barchart | `benchmark_aggregates` |
| Benchmark History tok/s over Time | Timeseries | `benchmark_aggregates`, multi-series |
| Live Interaction Latency (STT/LLM/TTS/Total) | Timeseries | `interactions` |
| Interaction Errors (Total, Errors, Error Rate %) | Stat | `interactions` (3 Queries) |

Ein Plugin-Bug im frser-sqlite-datasource v4.0.2 (`queryType: "time series"` liefert immer `"can not convert to wide series"`) wurde durch den Workaround `queryType: "table"` mit Grafana-Transformationen (`convertFieldType`, `partitionByValues`) umgangen (Entscheid D-43). Das Dashboard JSON ist unter `docs/grafana/dashboard_import.json` versioniert und via `curl -d @dashboard_import.json` reproduzierbar importierbar.

### Structured Logging

Alle Pipeline-Module nutzen Python stdlib `logging` mit `RotatingFileHandler` (5 MB, 5 Backups = max 25 MB). Log-Format: `%(asctime)s [%(name)s] %(levelname)s: %(message)s`. Konfigurierbar via Env-Vars (`LOG_LEVEL`, `LOG_DIR`, `LOG_MAX_BYTES`). Jede Interaktion wird nach Abschluss mit `log_interaction()` in der `interactions`-Tabelle erfasst.

---

## 6. Lessons Learned



### Was hat gut funktioniert

**Monolithischer MVP-Ansatz:** Der Entscheid, eine monolithische Pipeline statt Docker-Microservices zu bauen, war richtig. Er ermöglichte innerhalb weniger Stunden einen lauffähigen Prototyp (Log 005). Die Microservice-Architektur wäre für den MVP ein signifikanter Overhead gewesen.

**SQLite als universelle Datenschicht:** Die Entscheidung, eine einzige SQLite-Datenbank für Long-Term Memory, Interaction Logs und Benchmark-Ergebnisse zu verwenden (D-13, D-19, D-30), vereinfachte die Grafana-Integration erheblich. Eine Datenquelle für alle Panels.

**Streaming + per-sentence TTS:** Der grösste UX-Gewinn war die Kombination aus Ollama-Streaming und sofortigem TTS pro Satz. Die wahrgenommene Latenz sank dramatisch, da der Nutzer hört, während das Modell noch generiert.

**Datenbasierte Modellentscheidung:** Der systematische Benchmark mit 9 Modellen und konsistenten Metriken (tok/s, TTFT, deutsche Qualität) ermöglichte eine evidenzbasierte Entscheidung statt Bauchgefühl.

**lgpio für Pi 5:** Die frühe Erkenntnis, dass der Pi 5 mit dem RP1-Chip `gpiochip4` statt `gpiochip0` verwendet und daher lgpio statt gpiozero benötigt (D-04), verhinderte spätere Debugging-Stunden.

### Was schwieriger war als erwartet

**Faktenretention bei 1B-Modellen:** Ein 1-Milliarden-Parameter-Modell mit einem 512-Token-Kontextfenster verliert frühe Kontextinformationen nach wenigen Turns. Die Lösung — Facts Re-Injection direkt vor jeder User-Nachricht — funktioniert, ist aber ein Workaround für eine fundamentale Modellschwäche.

**Grafana + SQLite-Integration:** Die Kombination aus WAL-Mode (der Schreibrechte für Lesezugriffe erfordert), Linux-Gruppenberechtigungen und systemd `ProtectHome=yes` führte zu drei unabhängigen Fehlerquellen, die nacheinander gelöst werden mussten (Log 011). Zusätzlich ist der Time-Series-Modus des frser-sqlite-datasource Plugins v4.0.2 fundamental defekt — ein undokumentierter Bug.

**Thread-Tuning-Intuition:** Die Erkenntnis, dass `num_thread=3` auf einem 4-Core-System schneller ist als `num_thread=4`, war kontra-intuitiv. Die Ursache (Thread-Contention ohne freien Core für Ollama-Server und OS-Scheduler) war nach dem Benchmark klar, hätte aber ohne systematisches Messen nicht gefunden werden können.

**Team-Koordination und Infrastruktur:** SSH-Keys von Team-Mitgliedern konnten nicht vollständig eingesammelt werden (Blocker A-05). Der externe Zugriff via Uni-IoT-Netz blieb offen (A-06). Das Projekt lief daher hauptsächlich durch Yanick als Einzelperson auf dem Pi 5.

### Wichtigste technische Entscheide (Auswahl)

| Entscheid | Begründung |
|---|---|
| D-06: Monolithische Pipeline | Schnellerer MVP ohne Docker-Overhead |
| D-11: venv mit `--system-site-packages` | lgpio nur system-weit verfügbar (kein pip wheel auf arm64) |
| D-27: gemma3:1b statt gemma3:4b | 3.8 tok/s + 1.3s TTFT → mit Streaming bessere UX als grösseres Modell |
| D-28: Kimi Cloud nicht als Primary | Avg TTFT 11.7s (max 32.7s) — Wartezeit nicht akzeptabel für Voice-Assistenten |
| D-37: num_thread=3 | Sweet Spot auf Pi 5: freier Core für Ollama-Server + OS-Scheduler |
| D-40: Overclock 2.8 GHz | +32% tok/s bei moderatem Voltage; 3.0 GHz nur +3% bei doppeltem Risiko |
| D-48: Facts Re-Injection | Defense-in-Depth: Small Models verlieren frühen Kontext bei wachsender History |
| D-49: LLM-Warmup beim Start | Ollama entlädt Modelle nach 5 Min.; Warmup eliminiert Cold-Start-Latenz |

---

## 7. Ideen zur Fortführung

### Analogtelefon als physisches Interface

Das in Log 013 konzipierte Analogtelefon wäre die nächste sinnvolle Hardware-Erweiterung. Ein vertrautes Gerät mit klarer Bedienlogik (Hörer abnehmen = sprechen) würde die Hemmschwelle für Seniorinnen und Senioren erheblich senken. Der technische Aufwand ist überschaubar: Hook-Switch via GPIO ersetzt den PIR-Trigger, USB-Audio-Adapter für das Hörermikrofon, kleiner Verstärker (PAM8403) für die Hörermuschel. Software-seitig sind die Änderungen minimal — die Pipeline-API bleibt identisch. Eine vollständige technische Anleitung liegt unter `docs/how-to_analog-telephone.md`.

### Microservice-Architektur

Die Skeletons für fünf FastAPI-Services (stt-service, llm-service, action-service, tts-service, logger-dashboard) liegen unter `seniorvoice/services/` und stellen jeweils einen `/health`-Endpoint bereit. Nach Stabilisierung des MVP wäre der Split in Docker Compose-Services ein natürlicher nächster Schritt — insbesondere für Skalierbarkeit und unabhängige Updates einzelner Komponenten.

### Systemd-Services für Autostart

Aktuell muss die Pipeline manuell per SSH gestartet werden. Zwei systemd-Services würden Autostart beim Boot ermöglichen: Erst Ollama (mit Model Pre-Load zur Cold-Start-Eliminierung), dann die Pipeline (mit `Depends-on`-Abhängigkeit). Das würde SeniorVoice zu einem echten Standalone-Gerät machen, das ohne technische Betreuung läuft.

### Lokale Modelloptimierungen

- **Quantisierung:** gemma3:1b in Q2_K_M (ca. 400 MB) testen — potenzielle weitere Speedverbesserung bei akzeptabler Qualitätseinbusse
- **Grössere Modelle mit GGUF-Optimierung:** gemma3:4b mit `num_thread=3` und Overclock als Qualitätsalternative evaluieren
- **Wake-Word statt PIR:** openwakeword-Integration würde physische Bewegung als Trigger überflüssig machen

### Weitere Ausbaumöglichkeiten

- **Termineintrag via LLM:** Structured Output (JSON) für Kalendereinträge, die lokal in SQLite gespeichert werden
- **Medikamenten-Erinnerung:** Zeitgesteuerte TTS-Ankündigungen via systemd-Timer
- **Mehrsprachigkeit:** Piper TTS unterstützt weitere Sprachen; faster-whisper versteht 99 Sprachen
- **Datenschutz-Audit:** Netzwerktraffic-Analyse mit tcpdump zur Verifikation: kein Datenabfluss

---

## 8. Projektkosten und Hardware

Die vollständige Hardware-Beschaffung erfolgte über fünf Rechnungen (Digitec, Reichelt, BerryBase, bastelgarage.ch). Gesamtbetrag: **CHF 895.42**.

| Kategorie | Kosten |
|---|---|
| Prototyp-Komponenten (aktiv im MVP) | CHF 440.23 |
| Temporär für Testing (Sense HAT, GPIO Doubler) | CHF 65.97 |
| Nicht eingesetzt (AI HAT+, etc.) | CHF 356.29 |
| **Total** | **CHF 895.42** |

Hinweis: Logitech C920E Webcam und Sony SRS-XB23 Bluetooth-Lautsprecher waren bereits vorhanden und sind in den Beschaffungskosten nicht enthalten.

**Nachbaukosten (Kernkomponenten):** ca. CHF 440 — Details in `docs/hardware/Hardware-Beschaffung.pdf`.

### Kernkomponenten für Nachbau

| Komponente | Verwendungszweck |
|---|---|
| Raspberry Pi 5 (16 GB) | Hauptrechner |
| M.2 HAT+ Compact + Crucial P310 1 TB NVMe | Boot-Device mit hoher I/O-Leistung |
| PIR HC-SR501 | Wake-Trigger |
| Dupont Jumperkabel | GPIO-Verdrahtung (3 Kabel: VCC/GND/OUT) |
| USB-Mikrofon (Logitech C920E oder äquivalent) | Spracheingabe |
| Bluetooth- oder USB-Lautsprecher | Sprachausgabe |

---

## 9. Fazit

SeniorVoice erreicht das zentrale Projektziel: ein vollständig lokaler, datenschutzkonformer Sprachassistent auf Consumer-Hardware, der ältere Personen bei Alltagsfragen unterstützt — ohne Cloud-Abhängigkeit, ohne Smartphone-Voraussetzung, ohne Datenleck.

Das Hauptergebnis der technischen Arbeit ist ein **+174% Throughput-Anstieg** gegenüber dem Baseline-Setup, durch systematisches Benchmarking und die nicht-intuitive Erkenntnis, dass `num_thread=3` auf einem 4-Core-System effizienter ist als der Default von 4 Threads. Mit `gemma3:1b-prod` auf dem übergetakteten Pi 5 (2.8 GHz) erreicht das System **10.4 tok/s** bei **698ms TTFT** — eine User Experience, die messbar besser ist als Kimi k2.6 Cloud (11.7s TTFT im Durchschnitt, max 32.7s).

Die Pipeline ist end-to-end funktional: PIR-Trigger → Mikrofon → STT → lokales LLM → TTS → Bluetooth-Lautsprecher, mit persistentem Long-Term Memory, strukturiertem Logging und Grafana-Dashboard. Alle Daten bleiben auf dem Gerät.

Der Entscheid, mit einem Monolithen statt sofort mit Microservices zu starten (D-06), war rückblickend richtig. Die Modularisierung der Pipeline-Module (`llm_backend.py`, `interaction_log.py`, `logging_config.py`) entstand genau dann, als der Bedarf klar wurde — nicht spekulativ. Die Service-Skeletons und die saubere Modulstruktur ermöglichen den Microservice-Split als nächsten Schritt, wenn eine zweite Entwicklungsphase beginnt.

---

## 10. Links und Ressourcen

### Repository-Struktur

```
seniorvoice/
├── pipeline/          ← Aktiver MVP-Code (14 Python-Dateien)
├── services/          ← Microservice-Skeletons (5 Services, /health-Endpoint)
└── docs/
    ├── Projektdokumentation.md   ← Dieses Dokument
    ├── projektantrag.md          ← Ursprünglicher Projektantrag (März 2026)
    ├── grafana/                  ← Dashboard JSON (reproduzierbarer API-Import)
    ├── hardware/                 ← Datenblätter + Hardware-Beschaffung
    ├── how-to_analog-telephone.md ← Technische Anleitung Analogtelefon-Interface
    └── logs/
        ├── raspi5-yanick/        ← 14 Arbeitsprotokolle (Logs 001–014 + xxx)
        └── raspi4-testing-device/ ← Arbeitsprotokolle Pi 4
```

### Relevante Dateien

| Datei | Inhalt |
|---|---|
| `CLAUDE.md` | Projektarchitektur, Deploy-Workflow, Coding-Konventionen |
| `CONTEXT.md` | Aktueller Projektstand, Hardware-Status, Software-Stack, 50 Technische Entscheide (D-01 bis D-50) |
| `seniorvoice/pipeline/main.py` | Einstiegspunkt, CLI-Flags (`--no-pir`, `--once`) |
| `seniorvoice/pipeline/benchmark_models.py` | Benchmark-CLI mit SQLite-Logging und JSON-Export |
| `seniorvoice/docs/grafana/dashboard_import.json` | Grafana Dashboard (API-Import-Format) |
| `seniorvoice/docs/hardware/Hardware-Beschaffung.pdf` | Vollständige Kostentransparenz |

### Technologien

| Technologie | Version | Verwendung |
|---|---|---|
| Python | 3.13 | Gesamte Pipeline |
| faster-whisper | latest | Speech-to-Text (small, cpu, int8, de) |
| Ollama | 0.18.2+ | Lokale LLM-Inferenz |
| gemma3:1b-prod | Q4_K_M, 815 MB | Primäres Sprachmodell |
| Piper TTS | latest | Text-to-Speech (de_DE-thorsten-medium) |
| SQLite | stdlib | Memory, Interaction Logs, Benchmark-Ergebnisse |
| Grafana | 11.6.0 (arm64) | Performance-Dashboard |
| lgpio | — | GPIO auf Pi 5 (RP1-Chip, gpiochip4) |

---

*Erstellt am 28.06.2026 · SeniorVoice Team · ZHAW IoT Data Streaming & Analytics FS2026*
