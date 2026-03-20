# SeniorVoice — Work Packages
**Lebendige Aufgabenliste · wird nach jeder Session aktualisiert**

> **Regel:** Nach jeder Coding-Session erledigte Pakete mit ✅ markieren und Datum + Autor eintragen.  
> Claude liest diese Datei am Anfang jeder Session und weiss sofort wo wir stehen.

---

## Legende

| Symbol | Bedeutung |
|---|---|
| ⬜ | Offen |
| 🔄 | In Bearbeitung |
| ✅ | Abgeschlossen |
| ❌ | Blockiert |

---

## W05 — Infrastruktur & Setup (Modul 0)

| ID | Aufgabe | Status | Erledigt von | Datum |
|---|---|---|---|---|
| A-01 | Raspberry Pi 5 headless aufsetzen, SSH, UFW, Docker, Ollama | ✅ | Yanick | 19.–20.03.2026 |
| A-02 | docker-compose.yml Skeleton (alle 5 Services) | 🔄 | Yanick | — |
| A-03 | Branching-Strategie definieren + dokumentieren | ⬜ | — | — |
| A-04 | llama3.2:3b auf Pi pullen + Antwortzeit messen | ⬜ | — | — |
| A-05 | SSH-Keys für Sansone, Haris, Chris einrichten | ❌ | — | Blockiert: Keys ausstehend |
| A-06 | Externer SSH-Zugang via Uni IoT-Netz klären | ❌ | — | Blockiert: Prof. kontaktieren |

---

## W06 — STT Service (Modul 1)

| ID | Aufgabe | Status | Erledigt von | Datum |
|---|---|---|---|---|
| A-07 | stt-service: FastAPI Skeleton + /health + /transcribe | ⬜ | — | — |
| A-08 | faster-whisper small Modell integrieren | ⬜ | — | — |
| A-09 | Dockerfile arm64-kompatibel für stt-service | ⬜ | — | — |
| A-10 | USB-Mikrofon auf Pi anschliessen + testen | ⬜ | — | — |
| A-11 | PIR-Sensor (HC-SR501) via GPIO anschliessen + Wake-Trigger testen | ⬜ | — | — |
| A-12 | End-to-End Test: Mikrofon → /transcribe → JSON Output | ⬜ | — | — |

---

## W07 — LLM Service (Modul 2)

| ID | Aufgabe | Status | Erledigt von | Datum |
|---|---|---|---|---|
| A-13 | llm-service: FastAPI Skeleton + /health + /chat | ⬜ | — | — |
| A-14 | Ollama HTTP API Wrapper implementieren | ⬜ | — | — |
| A-15 | System-Prompt definieren (Scope: Alltagsassistenz DE) | ⬜ | — | — |
| A-16 | Intent-Erkennung testen (Termin vs. Info) | ⬜ | — | — |
| A-17 | Dockerfile für llm-service | ⬜ | — | — |

---

## W08 — TTS + Action Service (Modul 3 + 4)

| ID | Aufgabe | Status | Erledigt von | Datum |
|---|---|---|---|---|
| A-18 | tts-service: Piper TTS (de_DE-thorsten) containerisieren | ⬜ | — | — |
| A-19 | tts-service: /speak Endpoint + Audio-Ausgabe via Lautsprecher | ⬜ | — | — |
| A-20 | action-service: Intent-Router implementieren | ⬜ | — | — |
| A-21 | Use Case 1: Termineintrag in SQLite speichern | ⬜ | — | — |
| A-22 | Use Case 2: Info-Anfrage direkt via LLM beantworten | ⬜ | — | — |
| A-23 | logger-dashboard: SQLite Schema + Logging-Endpoint | ⬜ | — | — |

---

## W09 — End-to-End Integration (Modul 5)

| ID | Aufgabe | Status | Erledigt von | Datum |
|---|---|---|---|---|
| A-24 | Alle Services in docker-compose.yml zusammenführen | ⬜ | — | — |
| A-25 | End-to-End Test: Sprache → STT → LLM → TTS → Lautsprecher | ⬜ | — | — |
| A-26 | Sense HAT LED-Feedback (Idle / Listening / Processing) | ⬜ | — | — |
| A-27 | Performance-Messung: Latenz pro Service, Gesamtdauer < 8 Sek. | ⬜ | — | — |

---

## W10 — MVP Einfrierung

| ID | Aufgabe | Status | Erledigt von | Datum |
|---|---|---|---|---|
| A-28 | Bugfixing + finale Tests | ⬜ | — | — |
| A-29 | RAID-Log aktualisieren | ⬜ | — | — |
| A-30 | Arbeitsprotokoll finalisieren | ⬜ | — | — |
| A-31 | MVP einfrieren + Tag im Git setzen | ⬜ | — | — |

---

## W11–W12 — Stretch + Demo-Prep (Optional)

| ID | Aufgabe | Status | Erledigt von | Datum |
|---|---|---|---|---|
| A-32 | Grafana Dashboard ausbauen (M7) | ⬜ | — | — |
| A-33 | Sense HAT Temperatur-Wohlbefindenscheck (M6) | ⬜ | — | — |
| A-34 | Pi 5 Migration + llama3.2:3b Test (M12) | ⬜ | — | — |
| A-35 | Demo-Rehearsal (vollständig offline) | ⬜ | — | — |
| A-36 | Projektbericht finalisieren + abgeben | ⬜ | — | — |

---

## Offene Blocker

| ID | Beschreibung | Verantwortlich |
|---|---|---|
| A-05 | SSH-Keys von Sansone, Haris, Chris ausstehend | Yanick — Keys einsammeln |
| A-06 | Externer SSH via Uni IoT-Netz | Yanick — Prof. Weber kontaktieren |

---

*Letzte Aktualisierung: 20.03.2026 | Yanick*
