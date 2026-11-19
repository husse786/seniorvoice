# Begrüssung und Persona

Status: Entwurf. Mit Tests geprüft (`tests/test_greeting.py`), noch nicht mit Seniorinnen und Senioren.

## Entscheid (Hussein, 19.11.2026)

- Die Begrüssung ist **nicht fest im Code**. Das Gerät eröffnet das Gespräch beim Abheben selbst, aus Textbausteinen.
- Nie «Wie kann ich Ihnen helfen?». Stattdessen eine kleine, konkrete Frage, passend zur Tageszeit.
- Die Persona (Systemprompt) steht in einer Textdatei, die das Team ohne Programmieren ändert.

## Die zwei Dateien

| Datei | Was drin steht | Wann eine Änderung gilt |
|---|---|---|
| `pipeline/prompts/begruessung.txt` | Bausteine für den ersten Satz beim Abheben | beim nächsten Abheben |
| `pipeline/prompts/persona.txt` | wie das Sprachmodell spricht und was es nie tut | ab dem nächsten Satz |

Zeilen mit `#` sind Kommentare. Kein Neustart nötig.

## So entsteht die Begrüssung

Das Gerät setzt drei Teile zusammen und wählt pro Teil zufällig eine Zeile, nie zweimal hintereinander dieselbe:

1. **Gruss nach Tageszeit**, mit Namen aus `SENIOR_NAME` in `.env`: «Guten Tag, Frau Keller.»
2. **Nächster Termin heute**, nur wenn heute noch einer kommt (aus der lokalen Termin-Datenbank, keine Medikamente): «Heute um 15:30 Uhr haben Sie noch Coiffeur.»
3. **Eine kleine Frage**, allgemein oder zur Tageszeit: «Haben Sie schon zu Mittag gegessen?»

Das Sprachmodell ist dabei nicht beteiligt. Die Begrüssung kommt deshalb sofort und kann nichts erfinden. Danach weiss das Modell, was gesagt wurde, und versteht eine kurze Antwort wie «Ja, eine Suppe».

Klingelt das Telefon wegen einer Erinnerung, sagt das Gerät beim Abheben die Erinnerung und **keine** zusätzliche Begrüssung. Das Modell kennt die Erinnerung und kann auf «Ah ja, danke» eingehen.

Ausschalten (die Seniorin/der Senior spricht zuerst): `GREETING_ON_PICKUP=false` in `.env`. Dann begrüsst das Sprachmodell selbst, nach den Regeln in `persona.txt`.

## Datenschutz

Name und Termintitel werden nur vorgelesen. Die Begrüssung steht wie das ganze Gespräch nur im Arbeitsspeicher und verschwindet beim Auflegen. Sagt die Person nichts, wird aus der Begrüssung allein auch keine Notiz gemacht.

## Risiken

- Das kleine Modell (gemma3:1b) hält sich nicht immer an die Persona. «Wie kann ich helfen» kann trotzdem vorkommen. In den Tests darauf achten und die Persona nachschärfen.
- Eine Frage wie «Haben Sie schon gefrühstückt?» kann sich nach ein paar Tagen wiederholen. Mehr Zeilen in `begruessung.txt` machen es abwechslungsreicher.

## Offen (nicht jetzt)

- Gesprächsgedächtnis über mehrere Tage, das regelmässig gelöscht wird. Heute merkt sich das Gerät nur kurze Notizen für 7 Tage (A8).
