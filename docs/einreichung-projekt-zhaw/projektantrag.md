# SeniorVoice — Projektantrag
**Lokaler KI-Sprachassistent für ältere Personen**

IoT Data Streaming & Analytics · ZHAW FS 2026  
Team: Yanick · Teammitglied 3 · Teammitglied 1 · Teammitglied 2 | Betreuer: Christian Weber

---

## 1 Ausgangslage & Problemstellung

Ältere Personen — insbesondere ab 65 Jahren — sind zunehmend mit digitalisierten Alltagsprozessen konfrontiert, für die sie weder die Geräte noch die digitale Kompetenz besitzen. Gleichzeitig werden analoge Zugangswege (telefonische Terminvergabe, Schalter) abgebaut.

**Konkrete Alltagshürden:**
- Arzttermine und Dienstleistungen (Pediküre, Coiffeur, Behörden) werden zunehmend nur noch online oder über Apps buchbar
- Bestehende Sprachassistenten (Alexa, Siri, Google) sind cloudbasiert, datenschutzkritisch und nicht auf Senioren ausgelegt
- Abhängigkeit von Angehörigen für digitale Alltagsaufgaben wächst und fördert soziale Isolation
- Alzheimer-Anfangsstadium Patienten vergessen teilweise, welche täglichen Medikamente sie einnehmen müssen

Bestehende Lösungen scheitern an zwei Kernproblemen: sie erfordern entweder ein Smartphone/Tablet als primäres Interface, oder sie senden sensible Sprachdaten in externe Clouds. Für ältere Personen ist beides eine Barriere — technisch und datenschutzbezogen.

---

## 2 Projektidee & Zielsetzung

SeniorVoice ist ein vollständig lokaler, datenschutzkonformer KI-Sprachassistent auf Raspberry Pi, der älteren Personen bei digitalen Alltagsaufgaben hilft — ohne Smartphone, ohne Cloud, ohne technisches Vorwissen.

Das Gerät reagiert auf Bewegung (PIR-Sensor), hört zu (Mikrofon), versteht Deutsch (lokales Whisper-STT), verarbeitet die Anfrage mit einem lokalen Sprachmodell (Ollama LLM) und antwortet per Lautsprecher (Piper TTS). Alle Interaktionen werden lokal in SQLite gespeichert und in einem Grafana-Dashboard visualisiert.

**Erfolgskriterien:**
- Gesprochene Deutsch-Anfrage wird lokal verstanden und beantwortet (End-to-End < 8 Sek. auf Pi 4)
- Alle 5 Microservices laufen als Docker-Container auf dem Pi
- Mindestens 2 Use Cases vollständig implementiert (Termin-Logging + Allgemeine Info)
- Alle Daten bleiben lokal — kein Datenabfluss nach aussen nachweisbar
- Interaktionen vollständig in SQLite geloggt und via Grafana visualisiert

---

## 3 Technische Architektur

### 3.1 Systemübersicht

```
PIR-Sensor (GPIO) ──► Wake-Signal
Mikrofon (USB)    ──► [stt-service]       ──► Transkript (JSON)
                             │
                             ▼
                       [llm-service]       ──► Intent + Antwort (JSON)
                       (Ollama lokal)
                             │
                             ▼
                      [action-service]     ──► Routing: Termin / Info / Sensor
                             │
                             ▼
                       [tts-service]       ──► Audio ──► Lautsprecher
                             │
                             ▼
                  [logger-dashboard]       ──► SQLite ──► Grafana
```

Alle Services kommunizieren intern via HTTP/REST + JSON.  
Alle Services laufen auf dem Raspberry Pi innerhalb von Docker Compose.

### 3.2 Microservices

| Service | Technologie | Verantwortung | Port |
|---|---|---|---|
| stt-service | FastAPI + faster-whisper | Audio → Transkript (lokal) | 8001 |
| llm-service | FastAPI + Ollama (phi3 / llama3.2:3b) | Intent-Erkennung + Antworttext | 8002 |
| action-service | FastAPI | Routing: welche Aktion? Kalender / Info | 8003 |
| tts-service | FastAPI + Piper TTS (DE) | Text → Sprache (Lautsprecher) | 8004 |
| logger-dashboard | FastAPI + SQLite + Grafana | Logs speichern + visualisieren | 8005/3000 |

### 3.3 Hardware

| Komponente | Spezifikation | Zweck | Status |
|---|---|---|---|
| Raspberry Pi 4 (4 GB) | Modul-Hardware (geliehen) | Entwicklung + MVP-Demo | ✅ Vorhanden |
| Raspberry Pi 5 (16 GB) | Privat (Teammitglied 3) | Standalone-Prototyp / Stretch | ⏳ Anfragen |
| Sense HAT | Modul-Hardware (geliehen) | Temperatur, Luftfeuchtigkeit, LEDs | ✅ Vorhanden |
| USB-Mikrofon | ReSpeaker 2-Mic oder äquivalent | Spracheingabe | 🛒 Beschaffen |
| Lautsprecher | USB / 3.5mm | Sprachausgabe (TTS) | 🛒 Beschaffen |
| PIR-Bewegungssensor | HC-SR501 | Wake-on-Motion Trigger | 🛒 Beschaffen |
| AI Hat+ (optional) | Hailo-8 (Teammitglied 3 privat) | Whisper-Acceleration (Stretch) | ⏳ Anfragen |

**Hardware-Entscheid:** Der Pi 4 (Modul) wird für MVP und Entwicklung verwendet. Der Pi 5 (16 GB, privat) wird für den finalen Standalone-Prototypen eingesetzt. AI Hat wird ausschliesslich für Whisper-STT-Acceleration evaluiert — nicht für LLM-Workloads (CPU-Inferenz auf Pi 5 ist für 3B-Modelle performanter als Hailo-10H).

### 3.4 Datenpipeline

| Stufe | Input | Output | Service |
|---|---|---|---|
| Ingest | PIR-Trigger + Mikrofon-Audio | WAV-Datei (temporär) | GPIO-Handler |
| STT | Audio-Stream | Transkript (JSON) | stt-service |
| LLM | Transkript + System-Prompt | Intent + Antworttext (JSON) | llm-service |
| Action | Intent | Aktion ausgeführt / Antwort vorbereitet | action-service |
| TTS | Antworttext | Audio-Output via Lautsprecher | tts-service |
| Logging | Alle Interaktionen | SQLite-Eintrag + Grafana-Metric | logger-dashboard |

---

## 4 Scope & Modulare Entwicklungsstrategie

Das Projekt ist bewusst modular aufgebaut: ein erreichbarer MVP-Core bildet die Grundlage, auf der Erweiterungsmodule iterativ aufgebaut werden. Scope und Aufwand sind realistisch für ~100–120 Stunden über 13 Wochen (4 Personen, 6–8 h/Woche total).

### CORE — MVP
**Pflichtteil · Wochen 5–10 · ~60–70 h · Note 4 erreichbar**

**Modul 0 — Infrastruktur & Setup**
- Raspberry Pi 4 headless aufsetzen (SSH, Docker, docker-compose)
- Remote-Zugriff via Raspberry Pi Connect für alle 4 Teammitglieder einrichten
- Git-Repository erstellen, Branching-Strategie definieren
- VLAN / Netzwerkkonfiguration für sicheren Remote-Zugriff

**Modul 1 — Spracheingabe (STT)**
- stt-service: FastAPI + faster-whisper (tiny/base Modell)
- USB-Mikrofon anschliessen und testen
- PIR-Sensor (GPIO) als Wake-Trigger integrieren
- API-Endpoint: POST /transcribe → JSON {text, duration_ms}

**Modul 2 — Sprachverarbeitung (LLM)**
- Ollama auf Pi installieren, phi3-mini oder llama3.2:3b laden
- llm-service: FastAPI-Wrapper um Ollama HTTP API
- System-Prompt definieren: Scope auf Alltagsassistenz beschränken
- API-Endpoint: POST /chat → JSON {intent, response_text}

**Modul 3 — Sprachausgabe (TTS)**
- Piper TTS mit deutscher Stimme (de_DE-thorsten) containerisieren
- tts-service: FastAPI + Audio-Ausgabe via Lautsprecher
- API-Endpoint: POST /speak → Audio-Playback

**Modul 4 — Action-Routing & Logging**
- action-service: Intent-Router (Termin-Log / Info-Antwort)
- Use Case 1: Termineintrag lokal in SQLite speichern
- Use Case 2: Allgemeine Info-Anfrage (LLM antwortet direkt)
- logger-dashboard: Alle Interaktionen in SQLite, Grafana-Dashboard

**Modul 5 — End-to-End Integration**
- Alle Services in docker-compose.yml zusammenführen
- End-to-End-Test: Sprache → Transkript → LLM → Antwort → Lautsprecher
- Sense HAT LED-Feedback (Statusanzeige: Idle / Listening / Processing)
- Performance-Messung: Latenz pro Service, Gesamtdauer < 8 Sek.

### ERWEITERUNGEN
**Optional · Wochen 11–12 · nach MVP-Einfrierung W10**

| Modul | Beschreibung | Aufwand | Prio |
|---|---|---|---|
| M6 — Sense HAT Sensor | Temperatur-Wohlbefindenscheck via Sense HAT | ~6 h | Hoch |
| M7 — Grafana Dashboard | Latenz, Fehlerrate, Nutzungsstatistiken ausbauen | ~6 h | Hoch |
| M12 — Pi 5 Migration | System auf Pi 5 (16 GB) migrieren, llama3.2:3b testen | ~4 h | Mittel |
| M8 — Web-Scraping | Echte Terminbuchung (Arztpraxis-Website) | ~12 h | Tief |
| M9 — Wake-Word | openwakeword statt PIR | ~8 h | Tief |

---

## 5 Projektplan

W01–W04 wurden für Projektidee, Architekturentscheid, Hardwareevaluation und Projektantrag genutzt. Der technische Aufbau startet ab W05.

**Effektive Entwicklungswochen:** W05–W12 (8 Wochen) | W13 = Demo & Abgabe  
**MVP-Deadline:** Ende W10  
**Puffer:** W11–W12 für Stretch, Bugfixing, Demo-Vorbereitung, Doku-Finalisierung

| Woche | Phase | Inhalt / Meilenstein | Modul | Verantw. |
|---|---|---|---|---|
| W01–W04 | ✅ Abgeschlossen | Projektidee, Architektur, Hardwareevaluation, Projektantrag | — | Yanick |
| W05 | 🔧 Infra | Pi headless + Docker + docker-compose; Pi Connect; Repo-Setup | M0 | Yanick (Teammitglied 1) |
| W06 | 🎙 STT | stt-service: faster-whisper containerisiert; USB-Mikrofon + PIR; POST /transcribe | M1 | TBD |
| W07 | 🧠 LLM | llm-service: Ollama + phi3-mini auf Pi; POST /chat; erste Intent-Tests | M2 | TBD |
| W08 | 🔊 TTS + Action | tts-service: Piper TTS DE; action-service: 2 Use Cases; SQLite-Logger | M3 + M4 | TBD |
| W09 | 🔗 Integration | End-to-End: Sprache → STT → LLM → TTS → Lautsprecher; Performance-Messung | M5 | Alle |
| W10 | ✅ MVP | Bugfixing, Tests, Dokumentation; MVP eingefroren | — | Alle |
| W11 | 📈 Stretch | Grafana Dashboard (M7) + Sense HAT Temperatur-Check (M6) | M6 + M7 | TBD |
| W12 | 🎬 Demo-Prep | Demo-Rehearsal, Doku finalisieren, Projektbericht abgeben | — | Alle |
| W13 | 🏁 Abschluss | Finale Demo + Präsentation | — | Alle |

---

## 6 Sicherheit & Datenschutz

Privacy by Design ist ein nicht-verhandelbares Designprinzip. Alle Verarbeitung findet on-device statt.

| Bedrohung | Mitigation | Verantwortung |
|---|---|---|
| Dauerhafte Mikrofon-Aktivierung | PIR-Sensor als Hardware-Trigger — Mikrofon nur aktiv bei Bewegung | action-service |
| LLM Prompt Injection | System-Prompt mit hartem Scope; keine Shell/Dateisystem-Zugriffe | llm-service |
| Netzwerk-Exposition | Nur LAN-lokal; kein Port-Forwarding, kein Cloud-Upload | Docker-Netzwerk |
| Audiodaten-Persistenz | Keine Audiodateien gespeichert — nur anonymisierte Transkripte | logger-service |
| Remote-Zugriff | UFW + SSH Key-Auth; Pi Connect nur für Entwicklung | Infrastruktur |
| Unbefugter Dashboard-Zugriff | Grafana mit Passwort; API-Keys für interne Service-Kommunikation | logger-dashboard |

---

## 7 Team & Rollen

| Person | Schwerpunkt | Backup-Rolle |
|---|---|---|
| Yanick | Projektleitung, Architektur, Dokumentation, llm-service | action-service |
| Teammitglied 3 | Hardware (Pi 5 + AI Hat), stt-service, PIR-Sensor | tts-service |
| Teammitglied 1 | Pi-Setup, Docker-Infrastruktur, logger-dashboard | stt-service |
| Teammitglied 2 | tts-service, action-service, Grafana-Dashboard | llm-service |

**Arbeitsweise:** Raspberry Pi per SSH + Pi Connect für alle zugänglich → iterativ-kollaborative Entwicklung ohne physischen Gerätetausch. Dokumentation via RAID-Log (Excel) + Arbeitsprotokoll (Word/MD) auf MS Teams SharePoint.

---

## 8 Bezug zum Modul IoT Data Streaming & Analytics

| Modulinhalt | Umsetzung in SeniorVoice |
|---|---|
| Embedded Systems & Sensorik | Raspberry Pi 4/5, PIR-Sensor, Sense HAT, USB-Mikrofon |
| Netzwerk & Protokolle | HTTP/REST intern; lokales LAN; optional MQTT für Sensor-Events (Stretch) |
| Datenstreaming & Ingestion | Audio-Stream → STT-Service; PIR-Events → logger-service in Echtzeit |
| Datenanalyse | Intent-Erkennung via LLM; Schwellenwert-Checks via Temperatursensor |
| Visualisierung | Grafana-Dashboard: Interaktions-Logs, Latenz, Fehlerrate, Sensor-Zeitreihen |
| IoT-Security | Privacy by Design: lokale Verarbeitung, kein Cloud-Upload, API-Key-Auth |
| Ambient Assisted Living (AAL) | Kernthema des Projekts — explizit im Modul als Anwendungsbereich genannt |

---

## 9 Demo-Plan

Live-Demo am Semesterende (~15 Minuten), vollständig offline im Heimnetz:

1. Setup zeigen: Pi auf Tisch, Mikrofon, LED-Status via Sense HAT (Rot = Idle)
2. PIR triggert: Person tritt vor Gerät → LED Grün → System: "Wie kann ich helfen?"
3. Use Case 1 — Termin: Gesprochene Anfrage → Kalender-Eintrag → Bestätigung via Lautsprecher
4. Use Case 2 — Info: Allgemeine Frage → LLM antwortet lokal, klar und einfach
5. Dashboard zeigen: Alle Interaktionen in Grafana, Antwortzeiten, kein Datenabfluss
6. Stretch-Demo (falls bereit): Temperatursensor → Wohlbefindenscheck

**Fallback-Plan:**
- Falls Pi-Performance ungenügend: LLM auf Laptop im LAN, Pi als Edge-Device
- Falls Lautsprecher-Setup fehlt: Text-Output auf Terminal als Fallback
- Demo-Skript ist gescriptet und vorgängig mehrfach getestet (W12)

---

*Letzte Aktualisierung: März 2026 | SeniorVoice Team*
