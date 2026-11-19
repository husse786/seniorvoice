# E-Mail als Kanal für Hilfe und Familie (F4)

Status: Entwurf. Mit nachgebautem Mailserver getestet (`tests/test_email_channel.py`), noch nicht mit einem echten Postfach.

## Entscheid (Hussein, 19.11.2026)

- Hilfe- und Familien-Meldungen gehen **per E-Mail** (Telegram wird zu wenig genutzt).
- **«Ich kümmere mich» = auf die Hilfe-Mail antworten.** Das Gerät holt neue Mails selbst ab (IMAP) und liest dabei **nur Absender und Betreff**, nie den Text der Antwort. Kein offener Port am Gerät, kein Konto für die Kontaktperson.
- Ein Bestätigungslink ins Portal kommt erst als Zusatz, wenn es Server und Domain gibt (`docs/wireguard.md`, Produktivbetrieb).

## Ablauf

1. Hilfe-Knopf → Mail an die erste Kontaktperson. Betreff: «Hilfe-Knopf gedrückt [SV-12-a1b2c3d4]».
2. Die Kontaktperson antwortet mit beliebigem Text. Zählt nur, wenn die Antwort **von ihrer Adresse** kommt und den **Code im Betreff** trägt (der Code ist pro Meldung zufällig, also nicht zu erraten).
3. Das Gerät sagt «Sandra hat geantwortet und kümmert sich um Sie.» Im Portal steht die Meldung auf «erledigt».
4. Ohne Antwort nach 10 Minuten: nächste Kontaktperson, danach «Bitte rufen Sie 144 an» (A14).

Das Gerät fragt das Postfach nur ab, solange eine Hilfe-Meldung offen ist (höchstens alle 15 Sekunden, Codes verfallen nach 3 Stunden).

## Einrichten

1. **Eigenes Postfach für das Gerät** anlegen, nicht ein privates. Vorschlag: Infomaniak (Schweiz), z. B. `seniorvoice-geraet@…`. Serveradressen laut Infomaniak-Hilfe prüfen ([FAQ 2427](https://www.infomaniak.com/en/support/faq/2427/sync-your-emails-across-all-your-devices), [Ports](https://www.infomaniak.com/en/support/faq/468/understanding-mail-ports-and-protocols)).
2. In `.env` auf dem Gerät:
   ```
   CHANNEL=email
   MAIL_SMTP_HOST=mail.infomaniak.com
   MAIL_SMTP_PORT=587
   MAIL_IMAP_HOST=mail.infomaniak.com
   MAIL_IMAP_PORT=993
   MAIL_USER=seniorvoice-geraet@example.ch
   MAIL_PASSWORD=…
   ```
   Verbindungen laufen immer verschlüsselt (STARTTLS bzw. TLS). Das Passwort steht nur in `.env` auf dem Gerät.
3. Kontakte mit E-Mail-Adresse (mit Zustimmung, T3):
   ```bash
   python contacts_cli.py set "Sandra Keller|Tochter|sandra@example.ch" "Spitex Winterthur|Spitex|team@spitex.example"
   ```
4. Test: Hilfe drücken, Mail kommt an, darauf antworten, nach höchstens etwa 15 Sekunden sagt das Gerät Bescheid.

## In der Simulation

`CHANNEL=console` (Standard): Die Meldung erscheint im Feld «Kontakt-Handy» auf der Telefon-Seite, der Knopf «Ich kümmere mich» ersetzt die Antwort-Mail. Mit `CHANNEL=email` gehen in der Simulation echte Mails hinaus; die Meldung steht zusätzlich im Feld, bestätigt wird dann nur per Antwort-Mail.

## Datenschutz (DS-05)

Der Mail-Anbieter sieht Absender, Empfänger, Zeitpunkt und den kurzen Meldungstext («Frau Keller hat um 14:05 Uhr den Hilfe-Knopf gedrückt»), nie Gesprächsinhalte. Bei Familien-Nachrichten sieht er den Text, den die Seniorin/der Senior bewusst verschickt. Mails werden nicht Ende-zu-Ende verschlüsselt. Deshalb: Schweizer Anbieter, Meldungen kurz.

## Risiken

- E-Mail kommt nicht so verlässlich sofort an wie eine Push-Nachricht (Verzögerung, Spam-Filter). Die Weitergabe nach 10 Minuten und der Hinweis auf 144 bleiben deshalb wichtig. Kontaktpersonen sollten die Geräte-Adresse in ihre Kontakte aufnehmen.
- Wer das Postfach-Passwort hat, kann Meldungen lesen. Es gehört nur auf das Gerät und in den Team-Passwortspeicher.
