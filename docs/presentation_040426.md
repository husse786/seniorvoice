SeniorVoice — Status-Praesentation 04.05.2026
Modul: IoT Data Streaming & Analytics, ZHAW FS 2026 Team: Yanick, Chris, Sansone, Haris | Betreuer: Christian Weber Projektwoche: W11
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
* Bestehende Sprachassistenten (Alexa, Siri, Google) sind cloudbasiert und nicht auf Senioren ausgelegt
* Abhaengigkeit von Angehoerigen fuer digitale Alltagsaufgaben waechst → soziale Isolation 
Unsere Loesung: SeniorVoice
* Vollstaendig lokaler KI-Sprachassistent auf Raspberry Pi 5
* Kein Smartphone, kein Cloud-Upload, kein technisches Vorwissen noetig
* Privacy by Design: alle Daten bleiben auf dem Geraet
* Natuerliche Sprachinteraktion auf Deutsch — warmherzig, geduldig, kurze Antworte 
Architektur der technischen Lösung
Person tritt vor Geraet
   → PIR-Sensor erkennt Bewegung
   → Mikrofon nimmt Sprache auf
   → Sprache wird lokal transkribiert (STT)
   → KI versteht und antwortet (LLM)
   → Antwort wird vorgelesen (TTS)
   → Lautsprecher gibt Antwort aus
--------------------------------------------------------------------------------
2 — Was wurde gemacht? (3-4 Min, 3-4 Slides)
Hardware-Setup
Komponente	Status	Details
Raspberry Pi 5 (16 GB)	Laeuft	Headless, SSH, NVMe-SSD Boot (444 MB/s)
NVMe SSD (Crucial P310 1TB)	Laeuft	5.1x Speedup gegenueber SD-Karte
Logitech C920E Webcam	Laeuft	USB-Mikrofon fuer Spracheingabe
Sony SRS-XB23 Speaker	Laeuft	Bluetooth 5.0, A2DP, LDAC Codec
PIR HC-SR501	Laeuft	GPIO4, kalibriert — erkennt Personen im Raum
Software-Pipeline (MVP — End-to-End funktional)
Schritt	Technologie	Beschreibung
Audio-Aufnahme	sounddevice + numpy	Silence-Detection (RMS), stoppt nach 2s Stille
Speech-to-Text	faster-whisper (small, int8)	Lokale Transkription, Deutsch, laeuft auf CPU
Sprachmodell (LLM)	Moonshot Kimi API (k2.6)	Cloud-API (MVP); Ollama-Fallback vorbereitet
Text-to-Speech	Piper TTS (thorsten-medium)	Lokale Sprachsynthese, deutsche Stimme
Sensor-Trigger	lgpio (GPIO4)	PIR-Sensor als Hardware-Trigger
Architekturentscheid
* Monolithische Python-Pipeline statt Docker-Microservices fuer den MVP
* Grund: weniger Moving Parts, schnellerer Weg zum funktionierenden Prototyp
* Microservice-Skeletons existieren bereits in services/ — Split nach Validierung 
Zusaetzliche Features (ueber MVP hinaus)
* Session Memory: Multi-Turn-Konversation mit 5-Minuten-Timeout
* Long-Term Memory: SQLite-basiert — Assistent merkt sich Fakten ueber Benutzer
* Audio-Feedback: Aufsteigende/absteigende Chimes signalisieren "hoere zu" / "denke nach"
* Structured Logging: Python logging mit Rotation (5 MB x 5 Backups)
* Interaction Logs: Jede Interaktion mit STT/LLM/TTS-Timing in SQLite → Grafana-ready 
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
--------------------------------------------------------------------------------
3 — Live-Demo (3-5 Min, 1 Slide mit Demo-Ablauf)
Setup
* Pi 5 mit angeschlossenem USB-Mikrofon (C920E) und BT-Speaker (Sony SRS-XB23)
* Terminal via SSH sichtbar auf Beamer/Bildschirm
* PIR-Sensor oder Keyboard-Trigger (--no-pir Flag) 
Demo-Ablauf
Schritt 1 — System starten
cd ~/seniorvoice/pipeline
source ../.venv/bin/activate
export LLM_API_KEY=<key>
python main.py --no-pir --once
→ System meldet "Bereit" im Terminal
Schritt 2 — Interaktion ausfuehren
* ENTER druecken (Keyboard-Trigger) → Listen-Chime ertoeht
* Frage stellen, z.B.: "Welcher Monat ist der waermste in der Schweiz?"
* Stille-Erkennung stoppt Aufnahme automatisch
* Thinking-Chime → LLM verarbeitet
* Antwort wird ueber Lautsprecher vorgelesen
Schritt 3 — Memory demonstrieren (optional, 2. Durchlauf)
python main.py --no-pir
* Erste Interaktion: "Ich heisse Albert und bin pensioniert.”
* Zweite Interaktion: "Wie heisse ich und was ist mein Beruf?”
* → Assistent erinnert sich (Long-Term Memory)
Fallback-Plan
* Falls WLAN/API-Probleme: vorab aufgenommenes Video der Demo zeigen
* Falls BT-Speaker-Probleme: --no-pir + Terminal-Output zeigen (Text statt Audio)
* Falls Pi nicht verfuegbar: Screenshots + Architekturdiagramm erklaeren
--------------------------------------------------------------------------------
4 — Ausblick / Naechste Schritte (1 Min, 1 Slide)
Prioritaet	Was	Status
1	Lokales LLM via Ollama (kein Cloud-Abhaengigkeit)	Vorbereitet, noch nicht getestet
2	systemd-Service (Autostart beim Boot)	Ausstehend
3	Docker-Compose + Microservice-Split	Skeletons vorhanden
4	Grafana Dashboard (SQLite-Daten bereits vorhanden)	Ausstehend
5	Hardware Prototyp finalisieren	Ausstehend
 
--------------------------------------------------------------------------------
Zusammenfassung fuer Folie / Einzeiler (1min, 1 Slide)
SeniorVoice ist ein vollstaendig lokaler KI-Sprachassistent auf Raspberry Pi 5, der aelteren Personen auf Deutsch bei Alltagsfragen hilft — ohne Cloud, ohne Smartphone, ohne technisches Vorwissen. Volle Data-Privacy, komplett auf die Bedürfnisse älterer Menschen ausgerichtet. Die MVP-Pipeline (Mikrofon → STT → LLM → TTS → Lautsprecher) laeuft end-to-end, inklusive Bewegungserkennung, Gespraechsgedaechtnis und Audio-Feedback.


Ich habe die verschiedenen Kapitel jeweils mit einer Zeitdauer und Anzahl Slides versehen.
Probiere die Kapitel entsprechend dieser Struktur darzustellen.
Stell zudem sicher, dass das Problem Framing beim Kapitel Projektidee wissenschaftlich fundiert ist (nutze also die vorhandenen APA Zitierungen die jeweils in Klammern in den Fliesstext eingearbeitet sind, wenn du diese Fakten verwendest. Nutze in diesem Teil zudem Statistiken und stelle diese in Diagrammen dar.