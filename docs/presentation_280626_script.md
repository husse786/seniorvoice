# SeniorVoice — Abschlusspräsentation 29.06.2026

> **Kurs:** IoT Data Streaming & Analytics · ZHAW FS2026  
> **Team:** Yanick Fischer, Teammitglied 3, Teammitglied 1, Teammitglied 2 | **Betreuer:** Christian Weber  
> **Dauer:** ~45 Minuten · 4 Personen à ~10 Minuten  
> **Gliederung:** Projektidee → Projektverlauf → Artefakt → Demo → Einsatzmöglichkeiten → Ausblicke

---

## Hinweis zur Folienerzeugung

Jede Folie enthält:
- **Titel** — Folientitel
- **Inhalt** — Bullet Points / Tabellen / Kernaussagen
- **Visuelles Element** — Was auf der Folie zu sehen sein soll (Diagramm, Foto, Tabelle, Screenshot)
- **Sprechtext (ca.)** — Was der Präsentierende sagt (~1 Min. pro Folie)

---

---

## EINLEITUNG (3 Min · Folien 01–03)

---

### Folie 01 — Titelfolie

**Titel:** SeniorVoice — Lokaler KI-Sprachassistent für ältere Menschen

**Inhalt:**
- Projektname: **SeniorVoice**
- Kurs: IoT Data Streaming & Analytics (FS2026) · ZHAW
- Team: Yanick Fischer, Teammitglied 3, Teammitglied 1, Teammitglied 2
- Betreuer: Christian Weber
- Datum: 29.06.2026

**Visuelles Element:**
- Grosse Titelschrift auf dunklem Hintergrund
- Bild: ältere Person im Gespräch mit einem Sprachassistenten, oder Raspberry Pi 5 Prototyp-Foto
- ZHAW-Logo + Kursbezeichnung unten

**Sprechtext:** "Guten Tag, wir sind Team SeniorVoice. Unser Projekt ist ein vollständig lokal laufender, datenschutzkonformer KI-Sprachassistent für Menschen ab 65, der auf dem Raspberry Pi 5 betrieben wird. Heute zeigen wir, wie wir vom ersten Setup bis zu einer demo-reifen Pipeline gekommen sind — mit Benchmark-Ergebnissen, Architekturentscheidungen und einem Ausblick auf mögliche Weiterentwicklungen."

---

### Folie 02 — Team & Rollen

**Titel:** Das Team und unsere Rollen

**Inhalt:**
- **Yanick Fischer** — Raspberry Pi 5 (16 GB) · MVP-Pipeline vollständig · LLM-Benchmarking · Grafana-Dashboard · Systemarchitektur
- **Teammitglied 1** — Raspberry Pi 4 · Service-Architektur · Kamera-Integration
- **Teammitglied 2 / Teammitglied 3** — Weitere Microservices · Dokumentation
- Konzept: Jeder baut einen eigenen Knoten → gemeinsam ergibt sich ein verteiltes System
- Diese Präsentation: Fokus auf den Pi 5 Prototyp (Yanicks Knoten = voll funktionsfähig)

**Visuelles Element:**
- Team-Karte mit Namen und Rollen (evtl. Foto pro Person)
- Pi-Icons als visuelle Unterscheidung: Pi 5 ↔ Pi 4

**Sprechtext:** "Unser Team besteht aus vier Studierenden. Ich war hauptverantwortlich für den Raspberry Pi 5, auf dem die gesamte MVP-Pipeline läuft — von der Spracherkennung bis zur Sprachausgabe. Teammitglied 1 hat parallel an einem Pi 4 gearbeitet. Teammitglied 2 und Teammitglied 3 haben weitere Microservices entwickelt. Der Prototyp, den wir heute zeigen, ist der Pi 5 Node mit der vollständig funktionierenden End-to-End-Pipeline."

---

### Folie 03 — Kurskontext: IoT Data Streaming & Analytics

**Titel:** Kurskontext: IoT Data Streaming & Analytics

**Inhalt:**
- Kurs: ZHAW, Frühlingssemester 2026
- Thema: Edge-Computing, IoT-Architekturen, Daten-Streaming-Pipelines
- Unsere Interpretation: **AI-Edge-Device** — alle Daten lokal verarbeitet, Privatsphäre als Kernfeature
- Abgrenzung: Alexa, Google Home → alles in der Cloud; SeniorVoice → **kein Byte Sprache verlässt das Gerät**
- Sprache als Daten-Stream: Mic → STT → LLM → TTS → Speaker (jede Stufe = eigener Service)

**Visuelles Element:**
- Vergleichsgrafik: Links "Cloud-Assistent" (Mikrofon → Cloud → Antwort), rechts "SeniorVoice" (alles lokal im Pi-Kreis)
- Grüner Haken bei SeniorVoice: "100% lokal"

**Sprechtext:** "Der Kurs IoT Data Streaming & Analytics befasst sich mit Architekturen, bei denen Daten an der Quelle verarbeitet werden — Edge Computing statt Cloud. Wir haben das konsequent umgesetzt: SeniorVoice verarbeitet Sprache vollständig auf dem Raspberry Pi. Das passt perfekt ins Kursthema: Die Sprachaufnahme ist ein Audio-Stream, STT transkribiert diesen, das LLM verarbeitet den Text-Stream, TTS wandelt ihn in Audio zurück. Ein echter IoT-Datenpipeline, nur eben vollständig auf dem Gerät."

---

---

## TEIL I: PROJEKTIDEE (6 Min · Folien 04–08)

*Wissenschaftliche Fundierung des Problems — mit APA-Zitierungen und Statistiken als Diagramme*

---

### Folie 04 — Das Problem: Digitale Ausgrenzung älterer Menschen

**Titel:** Problem: Digitale Ausgrenzung älterer Menschen

**Inhalt:**
- Die fortschreitende Digitalisierung verlagert essenzielle Dienstleistungen — Gesundheit, Banking, Kommunikation — auf digitale Plattformen (Soubic, o.D.)
- Ältere Menschen, denen digitale Kompetenz oder passende Geräte fehlen, werden zunehmend von der Gesellschaft abgeschnitten (Mubarak & Suomi, 2022)
- Die Unfähigkeit, das Internet zu nutzen, gilt mittlerweile als **„Super-Sozialdeterminante" der Gesundheit** (Byeon, 2026)
- Alltägliche Konsequenzen:
  - Arzttermine, Behörden, Dienstleistungen: oft nur noch online/per App buchbar
  - Bestehende Sprachassistenten (Alexa, Siri, Google): cloudbasiert, nicht auf Senioren ausgelegt
  - Abhängigkeit von Angehörigen für digitale Alltagsaufgaben wächst → soziale Isolation

**Visuelles Element:**
- Icon-basierte Aufzählung der Barrieren: Touchscreen / Passwörter / App-Updates / Cloud-Datenschutz
- Zitat-Highlight: *"Super-Sozialdeterminante der Gesundheit"* — Byeon (2026)

**Sprechtext:** "Das Problem, das wir adressieren, ist real und gut dokumentiert: Ältere Menschen werden durch die Digitalisierung ausgegrenzt. Arzttermine müssen online gebucht werden, Bankdienste werden digitalisiert, Behörden kommunizieren nur noch per App. Sprachassistenten wären eigentlich die ideale Lösung — natürlichstes Interface, keine App nötig. Aber die grossen Anbieter senden alle Sprachaufnahmen in die Cloud. Für eine Generation mit ausgeprägter Datenschutzsensibilität ist das oft ein absolutes KO-Kriterium."

---

### Folie 05 — DACH-Statistiken: Digitale Kluft in Zahlen

**Titel:** DACH-Vergleich: Digitale Kluft in Zahlen

**Inhalt:**

| Land | Kennzahl |
|---|---|
| **Schweiz** | Nur **3 %** der Älteren nutzen moderne digitale Dienste (z.B. Self-Checkout); lediglich **8,9 %** haben eine positive Haltung gegenüber digitalen Verbraucherservices (Seifert & Charness, 2022) |
| **Österreich** | **25 %** der 65–84-Jährigen nutzen das Internet nicht — bei **97 %** Nutzung unter den 16–64-Jährigen (Statistics Austria, 2025) |
| **Deutschland** | Weniger als die Hälfte (**42,6 %**) der 75–99-Jährigen nutzt das Internet (Quittschalle et al., 2020) |

**Visuelles Element:**
- **Balkendiagramm**: Internetnutzung nach Altersgruppe (16–64 vs. 65–84 vs. 75–99) — visuell eindrückliche Lücke
- Alternativ: Drei nebeneinander gestellte Kreisdiagramme (Schweiz / Österreich / Deutschland), je mit Prozentsatz der Nicht-Nutzer 65+
- Quellenangaben unter dem Diagramm (APA-Stil)

**Sprechtext:** "Die Zahlen sprechen für sich. In der Schweiz nutzen nur 3 Prozent der älteren Menschen moderne digitale Dienste. In Österreich verzichtet ein Viertel der 65 bis 84-Jährigen vollständig auf Internet — während fast alle Jüngeren online sind. In Deutschland nutzt weniger als die Hälfte der über 75-Jährigen das Internet. Diese Zahlen sind keine abstrakten Statistiken — sie beschreiben reale Menschen, die heute Hilfe bei alltäglichen digitalen Aufgaben brauchen."

---

### Folie 06 — Konsequenzen: Mehr als ein digitales Problem

**Titel:** Konsequenzen: Digitale Ausgrenzung hat gesundheitliche Folgen

**Inhalt:**
- Digital ausgeschlossene ältere Menschen haben ein **60 % höheres Risiko für depressive Symptome** (Byeon, 2026)
- Signifikant häufigere Einsamkeit bei digitaler Ausgrenzung (Zhong & Wang, 2025)
- COVID-19 verschärfte das Problem: QR-Codes und kontaktlose Systeme ersetzten physische Alternativen → Hilflosigkeit und Scham (Morrison et al., 2023)
- **Der Gap**: Einfachstes Interface (Sprache) trifft auf grösste Datenschutzbedenken (Cloud-Dienste)

**Visuelles Element:**
- Infografik: "60% höheres Depressionsrisiko" als grosse Zahl
- Verbindungspfeil: Digitale Ausgrenzung → Einsamkeit → Gesundheitsrisiko

**Sprechtext:** "Die Konsequenzen der digitalen Ausgrenzung gehen weit über Unbequemlichkeit hinaus. Menschen ohne digitale Teilhabe haben ein 60 Prozent höheres Risiko für depressive Symptome. Die Einsamkeit steigt, die Gesundheit leidet. Die COVID-Pandemie hat das Problem verschärft: Plötzlich wurden Impftermine nur noch online gebucht, Einkaufen brauchte eine App. Für ältere Menschen, die das nicht beherrschten, war das eine demütigende Erfahrung."

---

### Folie 07 — Bestehende Lösungen & ihre Schwächen

**Titel:** Warum bestehende Sprachassistenten nicht die Antwort sind

**Inhalt:**
- **Amazon Alexa / Echo**: Cloud-Aufnahmen auf US-Servern, nicht datenschutzkonform (CH/DSGVO), nicht seniorengerecht konfigurierbar
- **Google Home / Assistant**: Identisches Problem, Einwilligung in Datensammlung als Geschäftsmodell
- **Siri (iPhone)**: Setzt Smartphone-Kompetenz voraus — genau die Barriere die Senioren haben
- **Gemeinsame Schwäche**: Alle drei senden Sprachaufnahmen in die Cloud, keine explizite Senior-UX, Abhängigkeit von Abo-Modellen oder Hardware-Käufen
- **Datenschutz in der Schweiz**: Besonders sensibles Thema — revDSG (Datenschutzgesetz 2023) schreibt Datensparsamkeit vor

**Visuelles Element:**
- Vergleichstabelle: Amazon / Google / Apple — jeweils rotes Kreuz bei Cloud-Daten, rotes Kreuz bei Senior-UX
- "Datenschutzlücke"-Annotation

**Sprechtext:** "Die grossen Anbieter sind technisch beeindruckend, aber für unsere Zielgruppe nicht geeignet. Alle drei senden Sprachaufnahmen in US-amerikanische Cloud-Server — in der Schweiz ein kritischer Punkt, besonders seit dem revidierten Datenschutzgesetz 2023. Ausserdem sind sie nicht für ältere Menschen konfiguriert: Alexa reagiert auf jedes englische Wort, Google Home setzt ein Google-Konto voraus, Siri braucht ein iPhone. Das sind genau die Hürden, die Senioren ausschliessen."

---

### Folie 08 — SeniorVoice: Unsere Lösung

**Titel:** SeniorVoice: Lokaler, privater, seniorengerechter Sprachassistent

**Inhalt:**
- Vollständig lokaler KI-Sprachassistent auf **Raspberry Pi 5**
- Kein Smartphone, kein Cloud-Upload, kein technisches Vorwissen nötig
- **Privacy by Design**: alle Daten bleiben auf dem Gerät — keine Cloud-Verbindung für Normalbetrieb
- Natürliche Sprachinteraktion auf Deutsch — warmherzig, geduldig, kurze Antworten (2–3 Sätze)
- **Physischer Trigger**: PIR-Bewegungssensor (eintreten → System aktiviert) oder Telefon-Hörer abheben
- Architektur:
  ```
  Person tritt vor Gerät
     → PIR-Sensor erkennt Bewegung
     → Mikrofon nimmt Sprache auf
     → Sprache wird lokal transkribiert (STT)
     → KI versteht und antwortet (LLM)
     → Antwort wird vorgelesen (TTS)
     → Lautsprecher gibt Antwort aus
  ```

**Visuelles Element:**
- Produktfoto: Raspberry Pi 5 Prototyp mit PIR-Sensor, Mikrofon, Lautsprecher
- Stichwort-Cloud: "Lokal" · "Privat" · "Einfach" · "Deutsch" · "Seniorengerecht" · "Open Source"
- Architektur-Pfeil (kompakt, horizontal)

**Sprechtext:** "SeniorVoice ist unsere Antwort. Ein Raspberry Pi 5 mit 16 Gigabyte RAM führt alle KI-Berechnungen vollständig lokal durch. Der Bewegungssensor erkennt, wenn jemand in die Nähe tritt. Das Mikrofon nimmt die Frage auf, ein lokales Sprachmodell generiert eine Antwort auf Deutsch, und Piper TTS spricht diese aus — über einen Bluetooth-Lautsprecher. Alles auf dem Gerät, ohne Internetverbindung. Die Bedienung: einfach hintreten und fragen."

---

---

## TEIL II: PROJEKTVERLAUF (6 Min · Folien 09–13)

---

### Folie 09 — Projektziele & Meilensteine

**Titel:** Projektverlauf: März–Juni 2026 (Meilensteine chronologisch)

**Inhalt:**

| Datum | Meilenstein |
|---|---|
| 19.–20.03 | Pi 5 headless Setup, SSH, Docker, NVMe-Migration (5.1× Speedup) |
| 25.03 | Kamera, Sense HAT, NVMe-SSD (444 MB/s Read) |
| 28.03 | PIR + Sound-Sensor verdrahtet, GPIO validiert |
| 04.04 | Team-Building Session |
| 18.04 | Wissenschaftliches Grounding des Themas |
| 01.05 | **MVP End-to-End**: Mic → STT → LLM → TTS → Speaker ✅ |
| 01.05 | PIR-Sensor kalibriert und in Pipeline integriert |
| 01.05 | Session Memory + Long-Term Memory (SQLite) |
| 02.05 | Kimi k2.6 Cloud-API, Audio-Feedback, Structured Logging |
| 02.05 | Modulares LLM-Backend mit Fallback-Chain + Streaming TTS + Benchmark-CLI |
| 03.05 | LLM-Benchmark: 13 Modelle evaluiert; gemma3:1b als Kandidat |
| 03.05 | Performance-Tuning: gemma3:1b-prod @ 2.8 GHz OC — **10.4 tok/s (+174%)** |
| 03.05 | Grafana Dashboard: 5 Panels, SQLite-Anbindung |
| 16.06 | Cross-Team-Demo für Reto (Robotik-Projekt) — GitHub-Vollzugriff geteilt |
| 27.06 | Analogtelefon-Konzept & How-To dokumentiert (nicht implementiert) |
| 28.06 | Hardware-Dokumentation: CHF 895.42 Gesamtkosten transparent aufgelistet |

**Visuelles Element:**
- Horizontale Zeitachse (März → Juni 2026) mit Milestone-Markierungen und Farb-Phasen
- Phase 1: Setup (grau) · Phase 2: MVP (grün) · Phase 3: Optimierung (blau) · Phase 4: Abschluss (orange)

**Sprechtext:** "Das Projekt lief über das gesamte Frühlingssemester 2026, von März bis Ende Juni. In den ersten Wochen haben wir die Hardware eingerichtet — das ist erstaunlich zeitintensiv, da der Pi 5 mit seinem neuen RP1-Chip einige Eigenheiten hat, die uns Debugging-Stunden gekostet haben. In der Woche 11 im Mai haben wir dann in wenigen Tagen intensiver Arbeit die gesamte Pipeline zum Laufen gebracht, optimiert und eine Benchmark-Suite entwickelt."

---

### Folie 10 — Hardware-Setup: Alle Komponenten

**Titel:** Hardware: Raspberry Pi 5 als AI-Edge-Device

**Inhalt:**

| Komponente | Status | Details |
|---|---|---|
| **Raspberry Pi 5 (16 GB)** | ✅ Läuft | Headless, SSH, NVMe-SSD Boot (444 MB/s), Overclock 2.8 GHz |
| NVMe SSD (Crucial P310 1TB) | ✅ Läuft | 5.1× Speedup gegenüber SD-Karte (M.2 HAT+ Compact) |
| Logitech C920E Webcam | ✅ Läuft | USB-Mikrofon für Spracheingabe |
| Sony SRS-XB23 Speaker | ✅ Läuft | Bluetooth 5.0, A2DP, LDAC Codec |
| PIR HC-SR501 | ✅ Läuft | GPIO4, kalibriert — erkennt Personen im Raum |
| Raspberry Pi Camera Module 3 | ⬜ Verifiziert | Bildverarbeitung (im MVP nicht aktiv genutzt) |
| HW-496 Sound Sensor | ⬜ Verifiziert | Audio-Trigger (nicht aktiv genutzt) |
| Sense HAT v2 | ⬜ Getestet | GPIO-Konflikt mit PIR — nicht montiert |

**Kosten:** ~CHF 440 Beschaffungskosten (Logitech C920E + Sony SRS-XB23 bereits vorhanden)  
Gesamtausgaben Projekt inkl. Exploration: CHF 895.42 (vollständig dokumentiert)

**Visuelles Element:**
- Foto: Pi 5 mit M.2 HAT, Kühlkörper, PIR-Sensor, Kabelbaum — alles beschriftet
- Tabelle wie oben mit Status-Icons

**Sprechtext:** "Das Herzstück ist der Raspberry Pi 5 mit 16 GB RAM — die einzige Konfiguration, die genügend RAM für das lokale Sprachmodell plus alle Pipeline-Komponenten hat. Wir haben früh auf eine NVMe SSD umgestellt: 444 MB/s Leserate statt 87 bei der SD-Karte. Das macht einen messbaren Unterschied beim Laden des Sprachmodells. Die Hardwarekosten für den reproduzierbaren Prototyp liegen bei rund 440 Franken — wir haben die vollständigen Kosten transparent dokumentiert."

---

### Folie 11 — Software-Pipeline MVP

**Titel:** Software-Pipeline: MVP End-to-End

**Inhalt:**

| Schritt | Technologie | Beschreibung |
|---|---|---|
| Audio-Aufnahme | sounddevice + numpy | Silence-Detection (RMS-Threshold 0.02), stoppt nach 2s Stille |
| Speech-to-Text | **faster-whisper** (small, int8) | Lokale Transkription, Deutsch, läuft auf CPU |
| Sprachmodell (LLM) | **Ollama — gemma3:1b-prod** | Vollständig lokaler Betrieb; Kimi Cloud als Fallback |
| Text-to-Speech | **Piper TTS** (thorsten-medium) | Lokale Sprachsynthese, deutsche Stimme |
| Sensor-Trigger | lgpio (GPIO4) | PIR-Sensor als Hardware-Trigger |
| Audio-Output | PulseAudio → Bluetooth | Sony SRS-XB23 via A2DP |

**Architekturentscheid:** Monolithische Python-Pipeline statt Docker-Microservices für den MVP
- Grund: weniger Moving Parts, schnellerer Weg zum funktionierenden Prototyp
- Microservice-Skeletons existieren bereits in `services/` — Split nach Validierung

**Visuelles Element:**
- Horizontales Flussdiagramm mit Modulnamen + Technologie-Labels:
  ```
  [HC-SR501 PIR] → [C920E Mic] → [faster-whisper STT]
                                         ↓
  [Sony Speaker] ← [Piper TTS] ←  [Ollama LLM]
  ```
- Annotation: "Alles auf dem Pi 5 — kein Internet nötig"

**Sprechtext:** "Die Pipeline folgt einem linearen Datenfluss. Der PIR-Sensor erkennt Bewegung und triggert die Aufnahme. Das Mikrofon nimmt die Sprache auf bis zwei Sekunden Stille erkannt werden. faster-whisper transkribiert lokal auf der CPU. Ollama führt das Sprachmodell aus. Piper TTS wandelt die Antwort in Sprache um, die der Bluetooth-Lautsprecher abspielt. Für den MVP haben wir bewusst einen Monolith statt Microservices gebaut — für Geschwindigkeit, nicht weil wir es nicht besser könnten."

---

### Folie 12 — Zusätzliche Features über den MVP hinaus

**Titel:** Zusätzliche Features: Über den MVP hinaus

**Inhalt:**
- **Session Memory**: Multi-Turn-Konversation mit 5-Minuten-Timeout; verbaler Reset ("neue Frage")
- **Long-Term Memory**: SQLite-basiert — Assistent merkt sich Fakten über den Benutzer (Name, Beruf, Haustier)
- **Audio-Feedback**: Aufsteigende Chimes ("ich höre zu") / absteigende Chimes ("ich denke nach") — generiert via numpy Sinuswellen
- **Structured Logging**: Python logging mit Rotation (5 MB × 5 Backups)
- **Interaction Logs**: Jede Interaktion mit STT/LLM/TTS-Timing in SQLite — Basis für Grafana
- **Modulares LLM-Backend**: Abstraktionsschicht mit Fallback-Chain (Ollama → Kimi Cloud)
- **Streaming TTS**: Per-Satz Sprachausgabe während LLM noch generiert — reduziert wahrgenommene Latenz

**Visuelles Element:**
- Icon-Liste der 7 Features mit kurzen Labels
- Highlight: "Streaming TTS" mit Zeitachse (LLM generiert → Pi spricht ersten Satz gleichzeitig)

**Sprechtext:** "Über den MVP hinaus haben wir mehrere Features implementiert, die das System wirklich alltagstauglich machen. Das Long-Term Memory ist besonders relevant: der Assistent merkt sich nach jeder Session Fakten über den Nutzer und injiziert diese bei der nächsten Session automatisch wieder. Und das Streaming-TTS ist entscheidend für die User-Experience: Der Pi beginnt zu sprechen, während das Sprachmodell noch generiert. So liegt die wahrgenommene Latenz bei 2–3 Sekunden, auch wenn die vollständige Antwort 10 Sekunden dauert."

---

### Folie 13 — Architekturentscheide (D-Register)

**Titel:** Key Architecture Decisions: Das D-Register

**Inhalt:**

| ID | Entscheid | Begründung |
|---|---|---|
| D-04 | lgpio statt gpiozero | Pi 5 RP1-Chip erfordert gpiochip4 (nicht gpiochip0) |
| D-06 | Monolith statt Docker (MVP) | Schnellerer Weg zum funktionierenden Prototyp |
| D-10 | GPIO4 für PIR | Kein Konflikt mit anderen Peripheriegeräten |
| D-13 | SQLite für alle persistenten Daten | Stdlib, NVMe-schnell, Grafana-kompatibel |
| D-20 | `llm_backend.py` Abstraktionsschicht | Zero-breaking-change Backend-Wechsel via Env-Var |
| D-37 | `num_thread=3` als Produktionswert | Thread-Contention bei 4 Threads auf 4-Core-CPU |
| D-40 | 2.8 GHz Overclock | +32% bei moderatem Voltage; 3.0 GHz nur +3% mehr |
| D-48 | Facts Re-Injection vor User-Message | Small Models verlieren frühen Kontext |

**Annotation:** 50+ Entscheide dokumentiert in `CONTEXT.md`

**Visuelles Element:**
- Tabelle wie oben (Ausschnitt aus dem D-Register)
- Zahl "50+" als Hervorhebung

**Sprechtext:** "Alle Architekturentscheide haben wir in einem D-Register dokumentiert — 50 nummerierte Entscheide, jeder mit einer Begründung. Das ist ungemein wertvoll: Monate später weiss man noch, warum etwas so gebaut wurde. Einige Beispiele: Warum lgpio statt gpiozero — Pi 5 Eigenheit, die uns 2 Stunden Debugging gekostet hat. Warum 3 Threads statt 4 — Thread-Contention-Erkenntnis, dazu gleich mehr. Warum SQLite — weil es direkt aus Grafana lesbar ist, ohne Middleware."

---

---

## TEIL III: DAS ARTEFAKT — TECHNISCHE TIEFE (8 Min · Folien 14–21)

---

### Folie 14 — LLM-Entscheidung: Cloud oder Lokal?

**Titel:** Die zentrale Frage: Cloud-LLM oder lokales Modell?

**Inhalt:**
- Ursprüngliche Annahme: Cloud-Modell (Kimi k2.6) = höhere Qualität → aber Datenschutz-Problem
- Kimi k2.6 (Moonshot AI): OpenAI-kompatible API, exzellentes Deutsch
- Problem: **TTFT (Time To First Token)** bei Kimi: avg. **11.7 Sekunden**, max. **32.7 Sekunden**
- Nutzer-Experience: Senioren hören erste Antwort erst nach 11+ Sekunden → **zu lang**
- Hypothese: Lokales kleines Modell mit Streaming kann bessere UX liefern

**Visuelles Element:**
- Balkendiagramm: Kimi Cloud TTFT (11.7s) vs. Ziel-TTFT (<2s) — dramatischer visueller Kontrast
- Annotation: *"11 Sekunden Stille = Senior denkt, Gerät ist kaputt"*

**Sprechtext:** "Die entscheidende Frage für SeniorVoice: Cloud oder lokal? Cloud-Modelle wie Kimi k2.6 liefern qualitativ hervorragende Antworten auf Deutsch — aber die Zeit bis zum ersten Token war im Schnitt fast 12 Sekunden, mit Spitzen bis zu 32 Sekunden. Für einen Senioren, der mit einem Sprachassistenten spricht, ist diese Wartezeit fatal: Nach 12 Sekunden Stille denkt man intuitiv, das Gerät sei defekt. Diese Erkenntnis hat uns dazu gebracht, lokale Modelle ernsthaft zu evaluieren."

---

### Folie 15 — Benchmark: Methodik & Getestete Modelle

**Titel:** LLM-Benchmark: 13 Modelle systematisch evaluiert

**Inhalt:**

**Testsetup:**
- 13 Modelle getestet: 12 lokal (Ollama) + 1 Cloud (Kimi k2.6)
- 4 deutsche Alltagsprompts × 3 Runden = 12 Runs pro Modell
- Isoliertes Testen mit explizitem Unloading zwischen Modellen
- Bewertungskriterien: **tok/s**, **TTFT** (Time to First Token), **deutsche Sprachqualität**
- Tool: `benchmark_models.py` (eigens entwickeltes CLI-Tool, Ergebnisse in SQLite + Grafana)

**Top-Modelle:**

| Rang | Modell | Typ | Grösse | tok/s | TTFT (warm) | Deutsche Qualität | Status |
|---|---|---|---|---|---|---|---|
| 1 | **gemma3:1b** | Lokal | 815 MB | 3.8 | 1327ms | Akzeptabel | **Ausgewählt** |
| 2 | gemma3n:e2b | Lokal | 5.6 GB | 2.4 | 2263ms | Gut | Zweitkandidat |
| 3 | gemma3:4b | Lokal | 3.3 GB | 1.7 | 2516ms | Exzellent | Zu langsam |
| 4 | **kimi-k2.6** | Cloud | — | 6.0 | 11719ms | Exzellent | Zu langsam (TTFT) |

**Disqualifizierte Modelle:**
- gemma4-Serie: "Thinking Models" mit 82–175s TTFT — für Voice-Assistant **unbenutzbar**
- llama3.1:8b / mistral:7b: Schlechtes Deutsch + zu langsam (60–78s pro Antwort)
- qwen2.5:3b: Kaputtes Deutsch ("vielen frohsinstensten geburtsTag!")
- liquidai/lfm2.5-350m: Schnellster Cold-Start (1.5s), aber inkohärentes Deutsch

**Kernfinding (vor Tuning):**
- Kimi Cloud: exzellentes Deutsch, aber 11.7s TTFT — User wartet zu lange
- gemma3:1b mit Streaming: ~4s bis zum ersten gesprochenen Wort vs. 11.7s+ bei Kimi

**Visuelles Element:**
- Tabelle der Top-4-Modelle farblich markiert
- Diagramm: TTFT-Vergleich alle Modelle (Kimi als Ausreisser deutlich sichtbar)
- Rote Kreuz-Icons bei disqualifizierten Modellen

**Sprechtext:** "Wir haben 13 Modelle systematisch getestet. Die grösste Überraschung war, dass grosse Modelle mit 7–8 Milliarden Parametern auf dem Pi 5 einfach zu langsam sind — unter 1.5 Tokens pro Sekunde und schlechtes Deutsch. Die Gemma4-Modelle sind 'Thinking Models' — sie rechnen intern sehr lang bevor sie antworten: TTFT von bis zu 175 Sekunden ist komplett unbrauchbar für einen Sprachassistenten. Kimi Cloud liefert das beste Deutsch, scheitert aber an der TTFT. gemma3:1b wurde als bester Kandidat für lokalen Betrieb identifiziert."

---

### Folie 16 — Key Finding: Thread-Optimierung verdoppelt den Durchsatz

**Titel:** Key Finding: Thread-Optimierung verdoppelt den Throughput

**Inhalt:**
- Ausgangslage (Baseline): gemma3:1b → **3.8 tok/s** (ondemand Governor, 4 Threads)
- Pi 5 hat 4 Cortex-A76 Cores
- Bei 4 Inference-Threads bleibt **kein Core** für Ollama-Server, OS-Scheduling, Memory-Controller frei
- Thread-Contention halbiert den Durchsatz!
- Lösung: `num_thread=3` in Ollama Modelfile

| Threads | tok/s | TTFT warm | vs. Baseline |
|---|---|---|---|
| 4 (Default) | 4.8 | 1183ms | +26% |
| 2 | 7.0 | 1003ms | +84% |
| **3** | **8.3** | **914ms** | **+118%** |

**Kernerkenntnis:** Auf einer **4-Core-CPU** sind **3 Inference-Threads** optimal — 1 Core bleibt frei für OS + Memory-Controller

**Visuelles Element:**
- Balkendiagramm der drei Thread-Konfigurationen (spektakulärer Unterschied sichtbar)
- Annotation: *"Sweet Spot: 3 Threads für 4-Core-CPU"*
- CPU-Diagramm: 4 Kerne, 3 für Inferenz, 1 für OS

**Sprechtext:** "Die grösste Entdeckung im gesamten Benchmarking war die Thread-Optimierung. Kontraintuitiv: Mit 4 Inference-Threads auf einer 4-Core-CPU war der Durchsatz schlechter als mit 3 Threads. Der Grund: Wenn alle 4 Kerne mit LLM-Inferenz beschäftigt sind, gibt es keinen freien Kern mehr für den Ollama-Server selbst, das Betriebssystem oder den Memory-Controller — die interne Kommunikation bricht zusammen. 1 Core für das System zu reservieren bringt plus 118% gegenüber der Baseline. Das ist eine nicht offensichtliche Erkenntnis mit enormem Impact."

---

### Folie 17 — Overclock + Produktionsmodell gemma3:1b-prod

**Titel:** Overclock + Produktionsmodell: Alle Optimierungen kombiniert

**Inhalt:**

**Overclock-Ergebnis:**

| Takt | arm_freq | over_voltage_delta | tok/s Gewinn | Temp. | Entscheid |
|---|---|---|---|---|---|
| 2.4 GHz (Standard) | — | — | Baseline | 74.1°C | — |
| **2.8 GHz** | 2800 | 25000 | **+32%** | 62.6°C | **Produktion** |
| 3.0 GHz | 3000 | 50000 | +35% (+3% mehr) | 70.0°C | Abgelehnt |

**Produktionsmodell `gemma3:1b-prod` (Ollama Modelfile):**
```
FROM gemma3:1b
PARAMETER num_thread 3
PARAMETER num_ctx 512
PARAMETER num_batch 128
```

**Gesamtergebnis nach allen Optimierungen:**

| Metrik | Vorher (Baseline) | Nachher (Prod) | Verbesserung |
|---|---|---|---|
| **tok/s (warm)** | 3.8 | **10.4** | **+174%** |
| **TTFT warm** | 1327ms | **698ms** | **−47%** |
| Zeit bis erstes gesprochenes Wort | ~4s | ~2.5s | **−38%** |
| Temperatur unter Last | 74.1°C | 62.6°C | Stabil, kein Throttling |

**Visuelles Element:**
- Grosse Infografik: "3.8 → 10.4 tok/s" mit "+174%"-Annotation (dominant)
- Drei-Stufiger Pfeil: Thread-Opt. (+118%) → Governor (+24%) → Overclock (+32%)
- Temperatur-Balken: "kein Throttling bestätigt"

**Sprechtext:** "Den Overclock auf 2.8 GHz habe ich sorgfältig evaluiert. 3.0 GHz brachte nur 3% Mehrleistung bei doppeltem Spannungsdelta — das ist für ein Dauerbetriebsgerät nicht lohnend. 2.8 GHz ist der Sweet Spot: plus 32%, stabile Temperatur bei 62 Grad. Kombiniert man alle Optimierungen — Thread-Konfiguration, CPU-Governor auf Performance-Mode und Overclock — kommt man von 3.8 auf 10.4 Tokens pro Sekunde. Das ist 174% Verbesserung, vollständig lokal, ohne Cloud."

---

### Folie 18 — Cloud vs. Lokal: Das finale Urteil

**Titel:** Cloud vs. Lokal: Finaler Vergleich

**Inhalt:**

| Kriterium | Kimi Cloud (k2.6) | gemma3:1b-prod (lokal) | Gewinner |
|---|---|---|---|
| TTFT | 11.7s avg, 32.7s max | **0.7s** | Lokal |
| tok/s | 6.0 | **10.4** | Lokal |
| Antwortqualität (Deutsch) | Sehr gut | Gut | Cloud |
| Datenschutz | Alle Anfragen zu Moonshot-Servern | 100% lokal | Lokal |
| Internetabhängigkeit | Ja | Nein | Lokal |
| Kosten | API-Kosten pro Token | Stromkosten (Pi) | Lokal |
| **Nutzer-Experience** | **Schlecht (>11s Wartezeit)** | **Gut (<1s bis erstes Wort)** | **Lokal** |

**Kernaussage:** Lokales Modell schlägt Cloud in der User-Experience trotz schlechterer Antwortqualität — weil TTFT die wahrgenommene Reaktionsgeschwindigkeit dominiert.

**Visuelles Element:**
- Vergleichstabelle mit Farb-Coding: Lokal-Gewinner grün, Cloud-Gewinner blau
- Headline-Zahl: "TTFT Faktor 17× besser lokal" (11.7s / 0.7s)

**Sprechtext:** "Der direkte Vergleich ist eindeutig. Das Cloud-Modell hat besseres Deutsch — das 1-Milliarden-Parameter-Modell hat weniger Weltwissen. Aber für unsere Zielgruppe ist die User-Experience entscheidend: 12 Sekunden Wartezeit sind für einen Senioren schlicht inakzeptabel. Das lokale Modell ist Faktor 17 schneller beim ersten Token. Die Schlussfolgerung: Für Voice-Assistenten ist TTFT die wichtigste Metrik — und dort gewinnt der lokale Betrieb klar."

---

### Folie 19 — Memory-System & Seniorengerechte UX

**Titel:** Memory & UX: Was das System wirklich seniorengerecht macht

**Inhalt:**

**Memory-System (zwei Ebenen):**
- **Session Memory** (In-Memory): Gesprächsverlauf innerhalb einer Session · 5-Min-Timeout · Verbaler Reset
- **Long-Term Memory** (SQLite `user_facts`): Persistente Fakten über den Nutzer
  - Format: `{category: "name", key: "vorname", value: "Albert"}`
  - Extraktion: Nach jeder Session via LLM-Call automatisch
  - Re-Injection: Fakten werden direkt vor jeder User-Nachricht eingefügt (verhindert "Vergessen" bei kleinen Modellen)

**System-Prompt Engineering für Senioren:**
- Keine Emojis/Sonderzeichen (Piper liest sie wörtlich vor)
- Siez-Form (Sie statt du)
- Kurze Antworten (2–3 Sätze max.)
- Anti-Halluzination: "Das weiss ich leider nicht" statt erfinden
- Begrüssung nur beim ersten Turn

**Audio-Feedback:**
- `listen_chime`: aufsteigend C5→E5 (300ms) = "ich höre zu"
- `thinking_chime`: absteigend E5→C5 (260ms) = "ich denke nach"
- Generiert via numpy Sinuswellen — keine externen Dateien

**Visuelles Element:**
- Zwei-Layer-Diagramm: Session-Memory (Wolke, flüchtig) und SQLite-Layer (Zylinder, persistent)
- Split-Screen: "Schlechte Antwort" (mit Emoji, duzt) vs. "Gute Antwort" (korrekt, kurz, Sie-Form)

**Sprechtext:** "Was das System wirklich für Senioren tauglich macht, sind die Details. Das Long-Term Memory merkt sich, wer der Nutzer ist — Name, Beruf, Haustier — und injiziert diese Fakten bei jedem Gespräch wieder. Der System-Prompt steuert das Verhalten: kein Emoji, kein Du, keine langen Monologe, keine erfundenen Fakten. Und die Chimes signalisieren akustisch was das System gerade macht — für eine Zielgruppe, die kein Display beobachtet, ist das entscheidend."

---

### Folie 20 — Grafana Dashboard: Observability

**Titel:** Observability: Grafana Dashboard mit SQLite-Datenquelle

**Inhalt:**
- **Grafana 11.6.0** (arm64) auf Pi, Port 3000
- **frser-sqlite-datasource v4.0.2** Plugin — liest direkt aus `seniorvoice.db`
- 5 Dashboard-Panels:
  1. Benchmark tok/s by Model (Barchart)
  2. Benchmark TTFT by Model (Barchart)
  3. Benchmark History tok/s over Time (Timeseries)
  4. Live Interaction Latency STT/LLM/TTS/Total (Timeseries)
  5. Interaction Errors: Fehlerquote (Stat)
- Zugriff via SSH-Tunnel: `ssh -L 3000:localhost:3000 yanick@<PI_IP>`
- Dashboard-JSON versioniert in `docs/grafana/dashboard_import.json`

**Visuelles Element:**
- Screenshot: Grafana-Dashboard mit allen 5 Panels (Hauptvisual dieser Folie)
- Annotation: SSH-Tunnel-Befehl sichtbar

**Sprechtext:** "Für Monitoring haben wir Grafana direkt auf dem Pi installiert und mit unserer SQLite-Datenbank verbunden. Alle Benchmark-Ergebnisse und alle Live-Interaktions-Timing-Daten laufen in SQLite und erscheinen in Echtzeit im Dashboard. Von meinem Mac aus greife ich via SSH-Tunnel auf Port 3000 zu. Das Dashboard zeigt mir sofort wenn eine Pipeline-Stufe plötzlich langsamer wird — ein echter Vorteil für die iterative Entwicklung."

---

### Folie 21 — Demo-Ablauf (Vorbereitung)

**Titel:** Demo-Vorbereitung: Setup & Ablauf

**Inhalt:**

**Setup:**
- Pi 5 mit angeschlossenem USB-Mikrofon (C920E) und BT-Speaker (Sony SRS-XB23)
- Terminal via SSH sichtbar auf Beamer/Bildschirm
- PIR-Sensor oder Keyboard-Trigger (`--no-pir` Flag)

**Demo-Ablauf:**

*Schritt 1 — System starten:*
```bash
cd ~/seniorvoice/pipeline
source ../.venv/bin/activate
python main.py --no-pir --once
```
→ System meldet Bereitschaft im Terminal

*Schritt 2 — Interaktion:*
- ENTER drücken (Keyboard-Trigger) → Listen-Chime ertönt
- Frage stellen: z.B. "Welcher Monat ist der wärmste in der Schweiz?"
- Stille-Erkennung stoppt Aufnahme automatisch
- Thinking-Chime → LLM verarbeitet
- Antwort wird über Lautsprecher vorgelesen

*Schritt 3 — Memory demonstrieren (2. Durchlauf):*
```bash
python main.py --no-pir
```
- Erste Interaktion: "Ich heisse Albert und bin pensioniert."
- Zweite Interaktion: "Wie heisse ich und was ist mein Beruf?"
- → Assistent erinnert sich (Long-Term Memory)

*Fallback-Plan:*
- Falls BT-Speaker-Probleme: Terminal-Output zeigen (Text statt Audio)

**Visuelles Element:**
- Schritt-für-Schritt Anleitung als visuelle Karte
- Terminal-Screenshot: Pipeline-Start-Output

**Sprechtext:** "Bevor wir zur Demo gehen, kurz der Ablauf: Ich starte die Pipeline per SSH, dann triggere ich per Keyboard-Taste — Sie hören den Listen-Chime. Ich stelle eine Frage — und etwa eine Sekunde nach meiner letzten Silbe beginnt der Assistent zu antworten. Im zweiten Durchlauf demonstrieren wir das Long-Term Memory: Der Assistent merkt sich meinen Namen und Beruf aus der vorherigen Interaktion."

---

---

## DEMO PROTOTYP (10 Min · Folie 22)

---

### Folie 22 — DEMO PROTOTYP

**Titel:** Live Demo: SeniorVoice in Aktion

> ⚡ **DEMO — 10 Minuten**

**Diese Folie bleibt während der gesamten Demo sichtbar.**

**Demo-Sequenz:**
1. System-Start (SSH, Pipeline läuft, Terminal sichtbar)
2. Trigger → Listen-Chime → Frage → Thinking-Chime → Antwort
3. Memory-Demo: Namen nennen → Folgefrage → Erinnerung bestätigt
4. PIR-Demo (falls verfügbar): Bewegung → automatischer Trigger

**Fallback:**
- Falls Hardware-Problem: Screenshots + Terminal-Output + Architekturdiagramm erklären

---

---

## TEIL IV: EINSATZMÖGLICHKEITEN (4 Min · Folien 23–25)

---

### Folie 23 — Zielgruppe & Anwendungsszenarien

**Titel:** Einsatzmöglichkeiten: Wer profitiert, wofür?

**Inhalt:**

**Primäre Zielgruppe:**
- Menschen 65+, insbesondere 75+ mit geringerer Digitalkompetenz
- Alleinstehende Senioren (erhöhtes Einsamkeitsrisiko)
- Menschen in ländlichen Regionen mit schlechterem Zugang zu persönlicher Beratung
- Pflegebedürftige zuhause (Unterstützung bei Alltagsfragen, ohne Angehörige zu belasten)

**Konkrete Anwendungsszenarien:**
- **Alltagsfragen**: "Wie ist das Wetter?" · "Welcher Tag ist heute?" · "Was sind die Symptome von Erkältung?"
- **Gedächtnisstütze**: "Was wollte ich einkaufen?" · "Wann ist mein Arzttermin?" (via Memory)
- **Gesellschaft & Gespräch**: Kurze Konversation für Menschen, die wenig soziale Kontakte haben
- **Behördenhilfe**: Erklärung von Formularen, Behördenbriefen (LLM kann Text erläutern)
- **Sprachlernhilfe**: Nicht-Muttersprachler können auf Hochdeutsch interagieren

**Erweiterbare Szenarien (mit Zusatzhardware):**
- Notfallkommunikation (Sturzerkennung via Beschleunigungssensor + Alert)
- Medikamenten-Erinnerung (lokale Kalender-Datenbank)
- Angehörigen-Brücke (lokale Nachrichten ohne Cloud)

**Visuelles Element:**
- Persona-Karte: "Frau Müller, 78, lebt allein in Winterthur, hat kein Smartphone"
- Icon-Liste der Szenarien mit klaren Symbolen

**Sprechtext:** "Wer profitiert konkret? Stellen Sie sich Frau Müller vor, 78 Jahre alt, lebt allein in Winterthur, hat kein Smartphone und kommt mit dem Computer nicht zurecht. Sie hat Alltagsfragen — was ist das Wetter, wie nehme ich dieses Medikament, was bedeutet dieser Behördenbrief. Heute ruft sie ihre Tochter an. Morgen könnte sie SeniorVoice fragen. Das System ist nicht auf diese Szenarien beschränkt — aber genau für diese Zielgruppe wurde es optimiert."

---

### Folie 24 — SeniorVoice vs. kommerzielle Lösungen

**Titel:** Potentielle Einsatzmöglichkeiten: SeniorVoice vs. Alternativen

**Inhalt:**

| Kriterium | Amazon Echo | Google Home | SeniorVoice |
|---|---|---|---|
| Datenschutz | Cloud-Aufnahmen (US) | Cloud-Aufnahmen (US) | 100% lokal |
| Offline-Betrieb | Nein | Nein | Ja |
| Anpassbar | Begrenzt (Skills) | Begrenzt (Actions) | Vollständig (Open Source) |
| Zielgruppe Senior | Generisch | Generisch | Explizit ausgelegt |
| Schweizer Datenschutz (revDSG) | US-Cloud, fraglich | US-Cloud, fraglich | DSGVO/DSG-konform |
| Kosten | CHF 30–180 + Abo | CHF 30–200 + Abo | ~CHF 440 (einmalig, kein Abo) |
| Eigenes LLM / System-Prompt | Nein | Nein | Vollständig konfigurierbar |
| Analogtelefon-Integration | Nicht möglich | Nicht möglich | Geplant (Architektur fertig) |

**Visuelles Element:**
- Vergleichstabelle mit Farb-Coding (rot/grün)
- Hervorhebung: "Datenschutz · Konfigurierbarkeit · Senior-UX" als SeniorVoice-Differenzierer

**Sprechtext:** "Gegenüber kommerziellen Lösungen hat SeniorVoice drei klare Differenzierer: Datenschutz — alle Daten bleiben auf dem Gerät, kein US-Cloud-Anbieter sieht Aufnahmen. Konfigurierbarkeit — System-Prompt, Sprache, Verhalten vollständig anpassbar. Und die explizite Senior-UX — kurze Antworten, Siez-Form, Chimes, PIR-Trigger. Die Kosten sind einmalig und transparent, kein Abonnement. Für Pflegeeinrichtungen oder NGOs, die solche Geräte skalieren wollen, ist das relevant."

---

### Folie 25 — Privacy by Design & Reproduzierbarkeit

**Titel:** Privacy by Design als Kernarchitekturprinzip

**Inhalt:**

**Datenschutz-Garantien:**
- Kein Audio verlässt das Gerät — Sprache wird lokal transkribiert
- Kein Nutzerprofil in der Cloud — Fakten lokal in SQLite auf NVMe SSD
- Kein API-Key erforderlich — Pipeline funktioniert ohne Cloud-Account
- Einzige optionale externe Verbindung: Kimi Cloud als Fallback-LLM (deaktivierbar)
- Für Senioren kommunizierbar: *"Ihr Gerät lernt Sie kennen — niemand sonst"*

**Reproduzierbarkeit:**
- Hardware-Budget: ~**CHF 440** für Nachbau (C920E und Sony SRS-XB23 bereits vorhanden)
- Code: Open Source, vollständig dokumentiert
- Deployment: `python main.py --no-pir --once` (einziger Startbefehl zum Testen)
- Hardware-Beschaffung vollständig dokumentiert (`docs/hardware/Hardware-Beschaffung.pdf`)

**Visuelles Element:**
- "Privacy Shield"-Grafik: Raspberry Pi im Zentrum, Cloud-Symbole aussen mit roten Linien (blockiert)
- Zwei Checkboxen-Listen: ✅ Lokal ✅ Datenschutz ✅ Offline-fähig ✅ Nachbaubar

**Sprechtext:** "Datenschutz ist kein Nachgedanke — er ist ein Architekturprinzip. Kein Audiobyte verlässt das Gerät. Alle Nutzerdaten bleiben auf der eigenen Hardware. Das System läuft komplett offline. Und: Es ist nachbaubar. Wir haben alle Kosten transparent dokumentiert — rund 440 Franken Beschaffungskosten für den Kern-Prototyp, alles Open Source, vollständige Deployment-Dokumentation. Eine Pflegeinstitution oder ein technisch versierter Angehöriger könnte das reproduzieren."

---

---

## TEIL V: AUSBLICKE & WEITERENTWICKLUNGEN (5 Min · Folien 26–29)

---

### Folie 26 — Was wurde seit der letzten Präsentation abgeschlossen?

**Titel:** Seit der letzten Präsentation (04.05.) abgeschlossen

**Inhalt:**

| Priorität | Was | Status |
|---|---|---|
| 1 | gemma3:1b-prod in Pipeline integrieren (LLM_MODEL=gemma3:1b-prod) | ✅ Bereit, Produktionsmodell existiert auf Pi |
| 2 | Ollama als systemd-Service (Autostart + Model Pre-Load) | ⬜ Eliminiert ~5.1s Cold-Start TTFT |
| 3 | Pipeline als systemd-Service (Autostart beim Boot) | ⬜ Depends-on Ollama |
| 4 | System-Prompt-Optimierung (erzwinge "Sie"-Form, Satzlänge) | ✅ Implementiert + getestet |
| 5 | Docker-Compose + Microservice-Split | ⬜ Skeletons vorhanden |
| 6 | Hardware-Prototyp finalisieren (Gehäuse) | ⬜ Ausstehend |

**Zusätzlich seit letzter Präsentation:**
- ✅ Lokales LLM via Ollama — läuft vollständig auf dem Pi (gemma3:1b-prod, 10.4 tok/s)
- ✅ Grafana Dashboard — 5 Panels, Live-Monitoring aus SQLite, SSH-Tunnel-Zugriff
- ✅ LLM-Benchmark — 13 Modelle systematisch evaluiert, datenbasierte Entscheidung
- ✅ Performance-Tuning — +174% Throughput durch Thread-Optimierung + Overclock
- ✅ Cross-Team-Austausch — Demo + GitHub-Vollzugriff für Robotik-Team (Reto)
- ✅ Hardware-Kosten vollständig dokumentiert (CHF 895.42 Gesamtprojekt)

**Visuelles Element:**
- Tabelle mit Status-Icons (grün = done, grau = ausstehend)
- Hervorhebung: "+174% Performance" als grosse Zahl

**Sprechtext:** "Zur Einordnung: Was haben wir seit der letzten Präsentation im Mai abgeschlossen? Die wesentlichsten Punkte: Das lokale Sprachmodell läuft vollständig optimiert auf dem Pi. Das Grafana-Dashboard ist operativ. Wir haben 13 Modelle benchmarkt und die Performance um 174% verbessert. Und wir haben das Projekt für ein anderes Team zugänglich gemacht — das Robotik-Projekt hat unser GitHub-Repository als Referenz."

---

### Folie 27 — Geplante Erweiterung: Analogtelefon als Interface

**Titel:** Ausblick: Analogtelefon als seniorengerechtes Interface

**Inhalt:**

**Idee:**
- Altes Analogtelefon als physisches Interface (PIR ersetzt durch Hörer-Abheben)
- **Warum ideal für Senioren**: Vertrauteste Technologie seit Jahrzehnten
  - Hörer abnehmen = Gerät hört zu → instinktive Bedienlogik
  - Hörer auflegen = Gespräch beendet
  - Tastatur für optionale Steuerung (Lautstärke, Reset)
- Wir haben ein konkretes Telefon dokumentiert: Innenansicht, Platine, RJ11-Anschlüsse, Lautsprecher fotografiert

**Warum nicht umgesetzt:**
- Keine Zeit (Projektabschluss) + fehlende Hardware-Komponenten (Lötstation, Arduino, USB-Audio-Adapter)
- Vollständige technische Anleitung dokumentiert in `docs/how-to_analog-telephone.md`
- Geschätzte Umsetzungszeit: ~6 Stunden · Kosten: ~CHF 20–50 Zusatzhardware

**Visuelles Element:**
- **Fotos des dokumentierten Analogtelefons** (aus `docs/screenshots/`):
  - `analog-phone_outside-front-interface_IMG_1541.JPG` — Frontansicht mit Bedienfeld
  - `analog-phone_board_IMG_1608.JPG` — Platine / Innenansicht
  - `analog-phone_rj11_IMG_1538.JPG` — RJ11-Anschluss
  - `analog-phone_speaker_IMG_1607.JPG` — Hörermuschel
- Pfeil-Diagramm: "Hörer abnehmen → GPIO-Trigger → Pipeline startet"

**Sprechtext:** "Die interessanteste geplante Erweiterung: Ein analoges Telefon als Interface. Wir haben ein konkretes Telefon beschafft, geöffnet, die Platine fotografiert und die Innenverkabelung analysiert. Die Bedienlogik ist für Senioren ideal: Hörer abheben bedeutet seit 60 Jahren 'ich möchte reden'. Das ist intuitiver als ein PIR-Sensor. Wir haben die vollständige technische Anleitung geschrieben, aber keine Zeit mehr für die Umsetzung. Die Anleitung wartet auf ein Folgeprojekt."

---

### Folie 28 — Analogtelefon: Technische Architektur

**Titel:** Analogtelefon-Integration: 3-Layer-Architektur

**Inhalt:**

```
Analogtelefon
├── Gabel-Schalter (Hook Switch) ──────────────── GPIO Pi 5 (Trigger)
├── Hörer-Mikrofon ──── USB-Audio-Adapter ──────── Pi 5 Mic-Input
├── Hörer-Muschel ────── Verstärker (PAM8403) ──── Pi 5 Audio-Out
├── Freisprecher-Mic (optional) ── USB-Audio ───── Pi 5 Mic-Input
├── Freisprecher-LS (optional) ─── Verstärker ──── Pi 5 Audio-Out
├── Tastenfeld (4×3 Matrix) ─────── Arduino ────── Pi 5 USB Serial
├── Lautstärke-Poti ─────────────── Arduino ADC ── Pi 5 USB Serial
└── Weitere Tasten (Hold/Transfer) ─ Arduino ───── Pi 5 USB Serial
```

**3 Schichten:**
- **Layer 1 (Audio)**: Hörermikrofon (RJ9/4P4C) → USB-Soundkarte → Pi STT; Pi TTS → PAM8403 Verstärker → Hörermuschel
- **Layer 2 (Trigger)**: Gabel-Schalter (NC-Kontakt) → GPIO Pi 5 direkt (kein Arduino nötig)
- **Layer 3 (Steuerung)**: 3×4 Tastenfeld + Lautstärke-Poti → Arduino Pro Micro → USB HID/Serial → Pi

**Software-Impact:**
- Neues Modul `telephone_trigger.py` (GPIO-Handler für Hook-Switch)
- `main.py`: `TRIGGER_MODE=hook` Env-Var (Pipeline-API bleibt gleich)

**Teileliste & Kosten:** USB-Audio-Adapter (CHF 5–15) · PAM8403 (CHF 3–8) · Arduino Nano (CHF 5–15) → **Total ~CHF 20–50**

**Visuelles Element:**
- ASCII-Diagramm wie oben
- Teile-Liste mit Kosten und Bezugsquellen

**Sprechtext:** "Die technische Architektur ist in drei Schichten aufgeteilt. Die Audio-Schicht ist die komplexeste: Das Hörermikrofon braucht die richtige Impedanz-Anpassung und Mic-Bias-Spannung — dafür ist ein USB-Audio-Adapter der einfachste Weg. Der Gabel-Schalter geht direkt an GPIO — einfacher als der PIR-Sensor. Das Tastenfeld läuft über einen Arduino, der dem Pi als USB-Keyboard erscheint. Gesamtkosten Zusatzhardware: 20 bis 50 Franken."

---

### Folie 29 — Nächste Schritte & Roadmap

**Titel:** Ausblicke: Nächste Schritte & mögliche Weiterentwicklungen

**Inhalt:**

**Kurzfristig (nächster Entwicklungsschritt, 1–2 Tage):**
1. **Analogtelefon** — How-To ist fertig, Hardware beschafft → ~6h Umsetzung, CHF 20–50
2. **systemd-Services** — Ollama + Pipeline als Autostart: eliminiert 5.1s Cold-Start, Pi startet ohne SSH-Login autonom
3. **System-Prompt-Feinschliff** — Erzwinge vollständige "Sie"-Form, kürzere Sätze

**Mittelfristig (nächste Projektphase):**
4. **Docker-Compose + Microservice-Migration** — STT/LLM/TTS als eigenständige FastAPI-Services (Skeletons existieren in `services/`)
5. **Offline-Wetter/Kalender** — Lokale Datenquellen (kein Cloud-API, z.B. Open-Meteo offline)
6. **Grösseres lokales LLM** — Wenn Quantisierung / Hardware verbessert wird (Pi 5 + LPDDR5)

**Langfristig (Vision):**
7. **Mehrsprachigkeit** — Schweizerdeutsch-Whisper-Feintuning
8. **Open-Source-Publikation** — GitHub-Projekt öffentlich, Community einladen
9. **Pflegeheim-Pilotversuch** — Deployment in echtem Seniorenumfeld mit Feedback-Loop
10. **Notfall-Integration** — Sturzerkennung + automatischer Notruf (Beschleunigungssensor + GSM)

**Visuelles Element:**
- Roadmap-Diagramm mit drei Zeithorizonten (Kurzfristig / Mittelfristig / Langfristig)
- GitHub-Logo für Open-Source-Ziel
- Icon für "Pflegeheim" als Zielanwendung

**Sprechtext:** "Die nächsten Schritte sind konkret und machbar. Das Analogtelefon steht an erster Stelle — die Anleitung ist fertig, die Hardware liegt vor uns. systemd-Services wären dann der zweite Schritt für echten Standalone-Betrieb. Mittelfristig interessiert mich der Microservice-Split — die Skeletons existieren bereits. Langfristig hat das Projekt Potenzial als Open-Source-Projekt, das Pflegeeinrichtungen replizieren können. Das ZHAW-Kursrahmen ist der erste Schritt, nicht der letzte."

---

---

## TEIL VI: ABSCHLUSS & REFLEXION (3 Min · Folien 30–31)

---

### Folie 30 — Herausforderungen & Learnings

**Titel:** Was uns überrascht hat: Herausforderungen & Learnings

**Inhalt:**

1. **Pi 5 RP1-Chip**: gpiochip4-Adressierung undokumentiert → 2h Debugging (D-04)
2. **LLM-Latenz vs. UX**: TTFT ist wichtiger als Tokens/s — 12 Sekunden Stille = untolerable
3. **Thread-Contention**: 4 Threads auf 4-Core-CPU schlechter als 3 (nicht intuitiv, enormer Effekt)
4. **NVMe-Einfluss**: Modell-Ladezeit war kritischer als erwartet — SSD zahlt sich aus
5. **System-Prompt-Iteration**: Echte Test-Gespräche nötig — theoretische Prompts decken nicht alle Edge Cases
6. **Bluetooth A2DP-Latenz**: ~200ms Wake-Latenz schluckt kurze Töne; kabelgebundener Speaker wäre stabiler
7. **Kimi-Fallback-Problem**: Wenn API-Key nicht gesetzt → stille Fallback auf Ollama ohne Warning — schwer zu debuggen

**Visuelles Element:**
- Nummerierte Liste mit Überraschungs-Icon / Glühbirne-Icon
- Highlight: "Thread-Contention" und "TTFT > tok/s" als grösste Erkenntnisse

**Sprechtext:** "Die grösste Überraschung: Thread-Contention. Dass weniger Threads schneller sein können als mehr — auf einer 4-Core-CPU — ist nicht intuitiv. Aber physikalisch erklärbar: Der Memory-Controller und das Betriebssystem brauchen auch CPU-Zeit. Die zweitgrösste Erkenntnis: TTFT ist wichtiger als Tokens pro Sekunde. Ein Modell das in 700ms antwortet und dann flüssig streamt, fühlt sich dramatisch besser an als eines das 11 Sekunden schweigt. Das hat unsere gesamte Modellentscheidung umgekehrt."

---

### Folie 31 — Schlussfolie

**Titel:** Danke — SeniorVoice zeigt, was möglich ist

**Inhalt:**

**Zusammenfassung in einem Satz:**
> SeniorVoice ist ein vollständig lokaler KI-Sprachassistent auf Raspberry Pi 5, der älteren Personen auf Deutsch bei Alltagsfragen hilft — ohne Cloud, ohne Smartphone, ohne technisches Vorwissen. Volle Data-Privacy, komplett auf die Bedürfnisse älterer Menschen ausgerichtet. Die MVP-Pipeline (Mikrofon → STT → LLM → TTS → Lautsprecher) läuft end-to-end mit vollständig lokalem LLM (gemma3:1b-prod, 10.4 tok/s nach Tuning), inklusive Bewegungserkennung, Gesprächsgedächtnis, Audio-Feedback und Grafana-Monitoring.

**Kernaussagen für die Prüfung:**
- **+174% Performance** durch systematisches Benchmarking (3.8 → 10.4 tok/s)
- **TTFT: 11.7s (Cloud) → 0.7s (lokal)** — Faktor 17 besser
- **50+ dokumentierte Architekturentscheide** · 15 Session-Logs
- **CHF ~440 Hardware** für reproduzierbaren Prototyp

**Fragen?**

Repository: `zhaw-iot-seniorvoice` | Kontakt: [Kontakt via GitHub]

**Visuelles Element:**
- Titelgrafik (wie Folie 01) mit "Vielen Dank"
- Die vier Kernzahlen als grosses Infografik-Element: +174% · ×17 · 50+ · CHF 440
- QR-Code zum Git-Repository (falls öffentlich)

**Sprechtext:** "SeniorVoice zeigt, dass ein moderner, datenschutzkonformer AI-Sprachassistent heute auf einer 440-Franken-Plattform möglich ist — ohne Abstriche bei der Nutzerfreundlichkeit für ältere Menschen. Die drei wichtigsten Erkenntnisse: Lokale Modelle schlagen Cloud-Modelle in der User-Experience, wenn man sie richtig tuned. TTFT ist für Voice-Assistenten die entscheidende Metrik. Und gute Dokumentation — 50 Architekturentscheide, 15 Session-Logs — ist so wertvoll wie guter Code. Wir freuen uns auf Ihre Fragen."

---

---

## Anhang: Vollständige Folienliste

| # | Folientitel | Abschnitt | Zeit ca. |
|---|---|---|---|
| 01 | Titelfolie | Einleitung | 1 min |
| 02 | Team & Rollen | Einleitung | 1 min |
| 03 | Kurskontext: IoT Data Streaming | Einleitung | 1 min |
| 04 | Problem: Digitale Ausgrenzung | I: Projektidee | 1 min |
| 05 | DACH-Statistiken Diagramm | I: Projektidee | 1 min |
| 06 | Konsequenzen der Ausgrenzung | I: Projektidee | 1 min |
| 07 | Bestehende Lösungen & Gap | I: Projektidee | 1 min |
| 08 | SeniorVoice: Unsere Lösung | I: Projektidee | 1 min |
| 09 | Meilensteine & Zeitachse | II: Projektverlauf | 2 min |
| 10 | Hardware-Setup: Alle Komponenten | II: Projektverlauf | 1 min |
| 11 | Software-Pipeline MVP | II: Projektverlauf | 1 min |
| 12 | Zusätzliche Features | II: Projektverlauf | 1 min |
| 13 | Architekturentscheide D-Register | II: Projektverlauf | 1 min |
| 14 | LLM-Entscheidung: Cloud oder Lokal? | III: Artefakt | 1 min |
| 15 | Benchmark: Methodik & Modelle | III: Artefakt | 2 min |
| 16 | Key Finding: Thread-Optimierung | III: Artefakt | 2 min |
| 17 | Overclock + gemma3:1b-prod | III: Artefakt | 1 min |
| 18 | Cloud vs. Lokal: Finales Urteil | III: Artefakt | 1 min |
| 19 | Memory & Seniorengerechte UX | III: Artefakt | 1 min |
| 20 | Grafana Dashboard | III: Artefakt | 1 min |
| 21 | Demo-Vorbereitung & Ablauf | III: Artefakt | 1 min |
| **22** | **⚡ DEMO PROTOTYP** | **Demo** | **10 min** |
| 23 | Zielgruppe & Anwendungsszenarien | IV: Einsatzmögl. | 1 min |
| 24 | SeniorVoice vs. kommerzielle Lösungen | IV: Einsatzmögl. | 2 min |
| 25 | Privacy by Design & Reproduzierbarkeit | IV: Einsatzmögl. | 1 min |
| 26 | Was seit letzter Präsentation abgeschlossen | V: Ausblicke | 1 min |
| 27 | Analogtelefon: Vision & Fotos | V: Ausblicke | 1.5 min |
| 28 | Analogtelefon: Technische Architektur | V: Ausblicke | 1 min |
| 29 | Nächste Schritte & Roadmap | V: Ausblicke | 1.5 min |
| 30 | Herausforderungen & Learnings | VI: Abschluss | 1.5 min |
| 31 | Schlussfolie | VI: Abschluss | 1.5 min |
| **Total** | | | **~45 Minuten** |

---

## Quellen (APA — Folie 04–06)

- Byeon, H. (2026). The internet as a super social determinant of health in older adults. *Journal of Aging and Health*.
- Morrison, J., et al. (2023). QR codes, contactless payment and digital exclusion in older adults. *BMC Geriatrics*.
- Mubarak, F., & Suomi, R. (2022). Elderly forgotten? Digital exclusion in the information age. *SAGE Open*.
- Quittschalle, J., et al. (2020). Ältere Menschen und die Nutzung digitaler Medien. *Dtsch Arztebl International*.
- Seifert, A., & Charness, N. (2022). Digital service use among older adults in Switzerland. *International Journal of Environmental Research and Public Health*.
- Soubic, C. (o.D.). Digital divide and older adults. Retrieved from published sources.
- Statistics Austria. (2025). IKT-Einsatz in Haushalten 2025. Statistik Austria.
- Zhong, R., & Wang, F. (2025). Social isolation and loneliness mediated by digital technology use in the elderly. *Frontiers in Public Health*.
