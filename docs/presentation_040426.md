SeniorVoice — Status-Praesentation 04.05.2026
Modul: IoT Data Streaming & Analytics, ZHAW FS 2026 Team: Yanick, Teammitglied 3, Teammitglied 1, Teammitglied 2 | Betreuer: Christian Weber Projektwoche: W11
--------------------------------------------------------------------------------
1 — Projektidee (2-3 Min, 3-4 Slides)
Problem: Digitale Ausgrenzung älterer Menschen
Die fortschreitende Digitalisierung verlagert essenzielle Dienstleistungen – Gesundheit, Banking, Kommunikation – auf digitale Plattformen (Soubic, o.D.). Ältere Menschen, denen digitale Kompetenz oder passende Geräte fehlen, werden dadurch zunehmend von der Gesellschaft abgeschnitten (Mubarak & Suomi, 2022). Die Unfähigkeit, das Internet zu nutzen, gilt mittlerweile als „Super-Sozialdeterminante" der Gesundheit (Byeon, 2026).
DACH-Vergleich: Digitale Kluft in Zahlen
Land	Kennzahl
Schweiz	Nur 3 % der Älteren nutzen moderne digitale Dienste (z. B. Self-Checkout); lediglich 8,9 % haben eine positive Haltung gegenüber digitalen Verbraucherservices (Seifert & Charness, 2022) [13, 14]
Österreich	25 % der 65–84-Jährigen nutzen das Internet nicht – bei 97 % Nutzung unter den 16–64-Jährigen (Statistics Austria, 2025) [10, 11]
Deutschland	Weniger als die Hälfte (42,6 %) der 75–99-Jährigen nutzt das Internet (Quittschalle et al., 2020) [12]
Konsequenzen
Digital ausgeschlossene ältere Menschen haben ein 60 % höheres Risiko für depressive Symptome (Byeon, 2026) und leiden signifikant häufiger unter Einsamkeit (Zhong & Wang, 2025). Die COVID-19-Pandemie verschärfte das Problem: QR-Codes und kontaktlose Systeme ersetzten physische Alternativen und führten bei Betroffenen zu Hilflosigkeit und Scham (Morrison et al., 2023). Alltägliche Herausforderungen sind:
* Aeltere Personen (65+) sind zunehmend mit digitalisierten Alltagsprozessen konfrontiert
* Arzttermine, Behoerden, Dienstleistungen: oft nur noch online/per App buchbar
* Bestehende Sprachassistenten (Alexa, Siri, Google) sind cloudbasiert und nicht auf Senioren ausgelegt
* Abhaengigkeit von Angehoerigen fuer digitale Alltagsaufgaben waechst → soziale Isolation
Unsere Loesung: SeniorVoice
* Vollstaendig lokaler KI-Sprachassistent auf Raspberry Pi 5
* Kein Smartphone, kein Cloud-Upload, kein technisches Vorwissen noetig
* Privacy by Design: alle Daten bleiben auf dem Geraet
* Natuerliche Sprachinteraktion auf Deutsch — warmherzig, geduldig, kurze Antworten
Architektur der technischen Lösung
Person tritt vor Geraet
   → PIR-Sensor erkennt Bewegung
   → Mikrofon nimmt Sprache auf
   → Sprache wird lokal transkribiert (STT)
   → KI versteht und antwortet (LLM)
   → Antwort wird vorgelesen (TTS)
   → Lautsprecher gibt Antwort aus
--------------------------------------------------------------------------------
2 — Was wurde gemacht? (3-4 Min, 5-6 Slides)
Hardware-Setup
Komponente	Status	Details
Raspberry Pi 5 (16 GB)	Laeuft	Headless, SSH, NVMe-SSD Boot (444 MB/s), Overclock 2.8 GHz
NVMe SSD (Crucial P310 1TB)	Laeuft	5.1x Speedup gegenueber SD-Karte
Logitech C920E Webcam	Laeuft	USB-Mikrofon fuer Spracheingabe
Sony SRS-XB23 Speaker	Laeuft	Bluetooth 5.0, A2DP, LDAC Codec
PIR HC-SR501	Laeuft	GPIO4, kalibriert — erkennt Personen im Raum
Software-Pipeline (MVP — End-to-End funktional)
Schritt	Technologie	Beschreibung
Audio-Aufnahme	sounddevice + numpy	Silence-Detection (RMS), stoppt nach 2s Stille
Speech-to-Text	faster-whisper (small, int8)	Lokale Transkription, Deutsch, laeuft auf CPU
Sprachmodell (LLM)	Ollama — gemma3:1b-prod (lokal)	Vollstaendig lokaler Betrieb; Kimi Cloud als Fallback
Text-to-Speech	Piper TTS (thorsten-medium)	Lokale Sprachsynthese, deutsche Stimme
Sensor-Trigger	lgpio (GPIO4)	PIR-Sensor als Hardware-Trigger
Architekturentscheid
* Monolithische Python-Pipeline statt Docker-Microservices fuer den MVP
* Grund: weniger Moving Parts, schnellerer Weg zum funktionierenden Prototyp
* Microservice-Skeletons existieren bereits in services/ — Split nach Validierung
Zusaetzliche Features (ueber MVP hinaus)
* Session Memory: Multi-Turn-Konversation mit 5-Minuten-Timeout
* Long-Term Memory: SQLite-basiert — Assistent merkt sich Fakten ueber Benutzer
* Audio-Feedback: Aufsteigende/absteigende Chimes signalisieren "hoere zu" / "denke nach"
* Structured Logging: Python logging mit Rotation (5 MB x 5 Backups)
* Interaction Logs: Jede Interaktion mit STT/LLM/TTS-Timing in SQLite
* Modulares LLM-Backend: Abstraktionsschicht mit Fallback-Chain (Ollama → Kimi Cloud)
* Streaming TTS: Per-Satz Sprachausgabe waehrend LLM noch generiert — reduziert wahrgenommene Latenz
* Grafana Dashboard: 5 Panels fuer Live-Monitoring (Benchmark-Vergleich, Interaction Latency, Errors)

LLM-Modellauswahl (13 Modelle evaluiert, 1 Slide)
Systematischer Benchmark aller verfuegbaren LLM-Modelle auf dem Raspberry Pi 5, um eine datenbasierte Modellentscheidung zu treffen.
Testsetup
* 13 Modelle getestet: 12 lokal (Ollama) + 1 Cloud (Kimi k2.6)
* 4 deutsche Prompts x 3 Runden = 12 Runs pro Modell
* Isoliertes Testen mit explizitem Unloading zwischen Modellen
* Bewertungskriterien: tok/s, TTFT (Time to First Token), deutsche Sprachqualitaet
Ergebnis-Tabelle (Top-Modelle)
Rang	Modell	Typ	Groesse	tok/s	TTFT (warm)	Deutsche Qualitaet	Status
1	gemma3:1b	Lokal	815 MB	3.8	1327ms	Akzeptabel	Ausgewaehlt
2	gemma3n:e2b	Lokal	5.6 GB	2.4	2263ms	Gut	Zweitkandidat
3	gemma3:4b	Lokal	3.3 GB	1.7	2516ms	Exzellent	Zu langsam
4	kimi-k2.6	Cloud	—	6.0	11719ms	Exzellent	Zu langsam (TTFT)
Disqualifizierte Modelle
* gemma4 Serie: "Thinking Models" mit 82–175s TTFT — fuer Voice-Assistant unbenutzbar
* llama3.1:8b / mistral:7b: Schlechtes Deutsch + zu langsam (60–78s pro Antwort)
* qwen2.5:3b: Kaputtes Deutsch ("vielen frohsinstensten geburtsTag!")
* qwen3:4b: Thinking Model, 4–12 Minuten pro Antwort
* liquidai/lfm2.5-350m: Schnellster Cold-Start (1.5s), aber inkohaerentes Deutsch
Kernfinding
* Kimi Cloud hat exzellentes Deutsch, aber 11.7s durchschnittliche TTFT (bis zu 32.7s) — User wartet zu lange
* gemma3:1b mit Streaming liefert bessere User Experience: ~4s bis zum ersten gesprochenen Wort vs. 11.7s+ bei Kimi

Performance-Tuning (1 Slide)
Nach der Modellauswahl: Systematisches Hardware- und Software-Tuning fuer maximale Inferenz-Geschwindigkeit.
Tuning-Hebel
Massnahme	Auswirkung	Details
CPU Governor → performance	+24%	Alle 4 Cortex-A76 Cores fix auf Maximalfrequenz statt dynamisch
num_thread=3 (statt 4 Default)	+118%	Bei 4 Threads auf 4 Cores: Thread-Contention — 1 Core frei fuer Ollama-Server + OS
Overclock 2.8 GHz	+32%	arm_freq=2800, over_voltage_delta=25000; Temp stabil bei 62.6°C
Overclock 3.0 GHz	nur +3% vs 2.8	Marginaler Gewinn bei doppeltem Voltage — abgelehnt fuer Dauerbetrieb
num_ctx=512	~0% tok/s	Kein messbarer Throughput-Gewinn, aber spart KV-Cache-Speicher
Gesamtergebnis
Metrik	Vorher (Baseline)	Nachher (Prod)	Verbesserung
tok/s (warm)	3.8	10.4	+174%
TTFT warm	1327ms	698ms	-47%
Zeit bis erstes gesprochenes Wort	~4s	~2.5s	-38%
Temperatur unter Last	74.1°C	62.6°C	Stabil, kein Throttling
Produktionsmodell: gemma3:1b-prod
* Konfiguration: num_thread=3, num_ctx=512, num_batch=128
* Hardware: CPU Governor performance, Overclock 2.8 GHz
* 10.4 tok/s bei 698ms TTFT — vollstaendig lokal, keine Cloud-Abhaengigkeit
* Kernerkenntnis: Thread-Count ist der dominante Hebel — Reduktion von 4 auf 3 Threads verdoppelt den Throughput auf einer 4-Core-CPU

Meilensteine (chronologisch)
Datum	Was
19.-20.03	Pi 5 headless Setup, SSH, Docker, NVMe-Migration
25.03	Kamera, Sense HAT, NVMe-SSD (5.1x read speedup)
28.03	PIR + Sound-Sensor verdrahtet, GPIO validiert
04.04.	Team-Building Session
18.04.	Wissenschaftliches Grounding des Themas
01.05	MVP End-to-End: Mic → STT → LLM → TTS → Speaker
01.05	PIR-Sensor kalibriert und in Pipeline integriert
01.05	Session Memory + Long-Term Memory (SQLite)
02.05	Kimi k2.6, Audio-Feedback, Structured Logging
02.05	Modulares LLM-Backend mit Fallback-Chain + Streaming TTS + Benchmark-CLI
03.05	LLM-Benchmark: 13 Modelle evaluiert; gemma3:1b als Kandidat identifiziert
03.05	Performance-Tuning: gemma3:1b-prod @ 2.8 GHz OC — 10.4 tok/s (+174%)
03.05	Grafana Dashboard: 5 Panels, SQLite-Anbindung, SSH-Tunnel-Zugriff
--------------------------------------------------------------------------------
3 — Live-Demo (3-5 Min, 1 Slide mit Demo-Ablauf)
Setup
* Pi 5 mit angeschlossenem USB-Mikrofon (C920E) und BT-Speaker (Sony SRS-XB23)
* Terminal via SSH sichtbar auf Beamer/Bildschirm
* PIR-Sensor oder Keyboard-Trigger (--no-pir Flag)
Demo-Ablauf
Schritt 1 — System starten
cd ~/seniorvoice/pipeline
source ../.venv/bin/activate
python main.py --no-pir --once
→ System meldet "Bereit" im Terminal
Schritt 2 — Interaktion ausfuehren
* ENTER druecken (Keyboard-Trigger) → Listen-Chime ertoeht
* Frage stellen, z.B.: "Welcher Monat ist der waermste in der Schweiz?"
* Stille-Erkennung stoppt Aufnahme automatisch
* Thinking-Chime → LLM verarbeitet
* Antwort wird ueber Lautsprecher vorgelesen
Schritt 3 — Memory demonstrieren (optional, 2. Durchlauf)
python main.py --no-pir
* Erste Interaktion: "Ich heisse Albert und bin pensioniert."
* Zweite Interaktion: "Wie heisse ich und was ist mein Beruf?"
* → Assistent erinnert sich (Long-Term Memory)
Fallback-Plan
* Falls BT-Speaker-Probleme: --no-pir + Terminal-Output zeigen (Text statt Audio)
* Falls Pi nicht verfuegbar: Screenshots + Architekturdiagramm erklaeren
--------------------------------------------------------------------------------
4 — Ausblick / Naechste Schritte (1 Min, 1 Slide)
Prioritaet	Was	Status
1	gemma3:1b-prod in Pipeline integrieren (LLM_MODEL=gemma3:1b-prod)	Bereit, Produktionsmodell existiert auf Pi
2	Ollama als systemd-Service (Autostart + Model Pre-Load)	Eliminiert ~5.1s Cold-Start TTFT
3	Pipeline als systemd-Service (Autostart beim Boot)	Depends-on Ollama
4	System-Prompt-Optimierung (erzwinge "Sie"-Form, Satzlaenge)	Ausstehend
5	Docker-Compose + Microservice-Split	Skeletons vorhanden
6	Hardware-Prototyp finalisieren (Gehaeuse)	Ausstehend

Bereits erledigt (seit letzter Praesentation)
* Lokales LLM via Ollama — laeuft vollstaendig auf dem Pi (gemma3:1b-prod, 10.4 tok/s)
* Grafana Dashboard — 5 Panels, Live-Monitoring aus SQLite, SSH-Tunnel-Zugriff
* LLM-Benchmark — 13 Modelle systematisch evaluiert, datenbasierte Entscheidung
* Performance-Tuning — +174% Throughput durch Thread-Optimierung + Overclock
--------------------------------------------------------------------------------
Zusammenfassung fuer Folie / Einzeiler (1min, 1 Slide)
SeniorVoice ist ein vollstaendig lokaler KI-Sprachassistent auf Raspberry Pi 5, der aelteren Personen auf Deutsch bei Alltagsfragen hilft — ohne Cloud, ohne Smartphone, ohne technisches Vorwissen. Volle Data-Privacy, komplett auf die Beduerfnisse aelterer Menschen ausgerichtet. Die MVP-Pipeline (Mikrofon → STT → LLM → TTS → Lautsprecher) laeuft end-to-end mit vollstaendig lokalem LLM (gemma3:1b-prod, 10.4 tok/s nach Tuning), inklusive Bewegungserkennung, Gespraechsgedaechtnis, Audio-Feedback und Grafana-Monitoring.


Ich habe die verschiedenen Kapitel jeweils mit einer Zeitdauer und Anzahl Slides versehen.
Probiere die Kapitel entsprechend dieser Struktur darzustellen.
Stell zudem sicher, dass das Problem Framing beim Kapitel Projektidee wissenschaftlich fundiert ist (nutze also die vorhandenen APA Zitierungen die jeweils in Klammern in den Fliesstext eingearbeitet sind, wenn du diese Fakten verwendest. Nutze in diesem Teil zudem Statistiken und stelle diese in Diagrammen dar.
