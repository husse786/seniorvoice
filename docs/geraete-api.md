# Geräte-Schnittstelle für das Portal (PR 10)

Status: Entwurf, im Code getestet (Tests mit echtem HTTP auf dem Rechner), am Gerät und mit einem Portal noch nicht geprüft.

Grundlage: Entscheide B4, B5, A16–A18 (14.11.2026) und `05_SOLL_Architektur.md` Kap. 4.6 im Konzept-Repo.

## Was sie macht

- Das Portal speichert keine Inhalte. Es holt Termine, Erinnerungsstatus und den Help-Verlauf bei jedem Aufruf **live** von dieser Schnittstelle (B4).
- Antwortet ein Gerät nicht, zeigt das Portal «offline seit …» aus dem Zeitpunkt der letzten Antwort (A16, A18). Das Gerät selbst muss dafür nichts speichern.
- Angehörige und Spitex sehen **Termine, Erinnerungsstatus und (wenn freigegeben) den Help-Verlauf**. Keine Gespräche, kein Gedächtnis, keine Rat-Fragen, keine Rückrufe (diese entstehen aus Gesprächen). Admin sieht nur Technik (B5).
- Jeder Termin zeigt, **wer ihn eingetragen hat**. Ändern und löschen darf nur diese Person. Termine der Seniorin/des Seniors (ohne Portal-Konto eingetragen) ändert niemand über das Portal (B5).
- **Doppelte Prüfung:** das Portal prüft die Rolle, das Gerät prüft selbst die Freigabeliste auf dem Gerät.
- **Zugriffsprotokoll auf dem Gerät:** jede Anfrage des Portals (wer, wann, welche Funktion, Ergebnis), ohne Inhalte. Anfragen ohne gültigen Gerätetoken werden nicht in die Datenbank geschrieben (sonst könnte jeder im Netz sie füllen), nur höchstens einmal pro Minute im Systemprotokoll vermerkt. Jede Person sieht ihre eigenen Einträge, Admin alle. Frist 30 Tage als Vorschlag (DS-07 offen, `AUDIT_RETENTION_DAYS`).
- Kein Posteingang (A17): Family und Help laufen weiter über den Kanal.

Eigenständiger Dienst (`device_api.py`), nur Python-Standardbibliothek, getrennt vom Telefon (kein Audio, kein GPIO, kein LLM). Fällt die Schnittstelle aus, funktionieren Telefon, Erinnerungen und Help weiter.

## Einrichten am Gerät

1. Gerätetoken erzeugen:
   ```bash
   cd ~/seniorvoice/pipeline && . ../.venv/bin/activate
   python device_api_cli.py token
   ```
   Den Token sicher an das Portal übergeben (nur einmal angezeigt). Die ausgegebene Zeile `DEVICE_API_TOKEN_SHA256=…` in `.env` eintragen. Auf dem Gerät liegt nur der Hash.
2. In `.env` die Tunnel-Adresse eintragen, z. B. `DEVICE_API_HOST=100.x.y.z` (Adresse der Tunnel-Schnittstelle, OA-09). Nur eine IP-Adresse, kein Name; `0.0.0.0`, `::` und ähnliche werden abgelehnt: das Gerät soll nur über den Tunnel erreichbar sein. Standard `127.0.0.1` (nur lokal, zum Testen).
3. Freigaben **mit Zustimmung der Seniorin/des Seniors** eintragen (das Portal kann sich selbst keine Freigabe geben):
   ```bash
   python device_api_cli.py grant sandra.keller "Sandra Keller" angehoerige --help-visible --senior-consent
   python device_api_cli.py grant spitex.mueller "M. Müller (Spitex)" spitex --senior-consent
   python device_api_cli.py grant admin.team "Projektteam" admin --senior-consent
   python device_api_cli.py list
   python device_api_cli.py revoke sandra.keller      # widerrufen
   ```
   Die Kennung (`sandra.keller`) muss der Konto-Kennung im Portal entsprechen. `--help-visible` nur für Help-Kontaktpersonen.
4. Dienst starten:
   ```bash
   sudo cp ~/seniorvoice/deploy/seniorvoice-api.service /etc/systemd/system/
   sudo systemctl daemon-reload && sudo systemctl enable --now seniorvoice-api
   journalctl -u seniorvoice-api -f
   ```
5. Prüfen (auf dem Gerät, mit `DEVICE_API_HOST=127.0.0.1`):
   ```bash
   curl -s -H "Authorization: Bearer <token>" -H "X-Person-Id: sandra.keller" http://127.0.0.1:8770/v1/status
   ```

## Anfragen

Jede Anfrage braucht `Authorization: Bearer <Gerätetoken>` (das Portal) und `X-Person-Id: <Konto>` (die Person im Portal). Antworten sind JSON. Zeiten, die Menschen eingeben, sind Schweizer Ortszeit im Format `JJJJ-MM-TT HH:MM`.

| Anfrage | Wer | Inhalt |
|---|---|---|
| `GET /v1/status` | alle | `api`, `device_time` (UTC), `uptime_s` |
| `GET /v1/appointments` | Angehörige, Spitex | Termine und Medikamente mit `created_by`, `own`, Erinnerungen mit Status (`geplant`, `klingelt`, `bestaetigt`, `verpasst`) |
| `POST /v1/appointments` | Angehörige, Spitex | `{"title", "due_local", "kind": "termin"\|"medikament", "pre_minutes"}` → `201 {"id"}` |
| `PUT /v1/appointments/<id>` | nur wer eingetragen hat | `{"title"?, "due_local"?, "pre_minutes"?}`. Nur Text geändert: Erinnerungen behalten ihren Status. Neue Zeit: Erinnerungen werden neu geplant, die gewählte Vorerinnerung bleibt |
| `DELETE /v1/appointments/<id>` | nur wer eingetragen hat | löscht sofort (secure_delete) |
| `GET /v1/help` | Angehörige, Spitex mit `--help-visible` | Help-Verlauf: Zeit, Status, zugestellt, quittiert von |
| `GET /v1/audit` | alle | eigene Protokolleinträge; Admin: alle |

Fehler: `401` falscher Token, `403` keine Freigabe oder keine Berechtigung, `404` unbekannt, `400` ungültige Eingabe (auch: Zeit in der Vergangenheit, mehr als 2 Jahre voraus oder wegen Zeitumstellung nicht existent). Nach einem Fehler schliesst das Gerät die Verbindung.

Wird die Zeit eines Termins geändert oder der Termin gelöscht, während er gerade klingelt, hört das Klingeln innerhalb einer Sekunde auf.

## Offen (für das Team)

- **Tunnel (OA-09) und Ort des Portals (OA-13):** Die Schnittstelle ist dafür neutral; sie hört auf der eingetragenen Adresse. Verschlüsselung liefert der Tunnel, die Schnittstelle selbst spricht kein TLS.
- **Vertrauen ins Portal:** Das Gerät prüft, ob die Person freigegeben ist, glaubt dem Portal aber, *wer* die Person ist. Ein kompromittiertes Portal könnte damit als jede freigegebene Person dieses Geräts handeln (nicht als Fremde). Ausbau, falls nötig: vom Portal signierte Personen-Token mit kurzer Gültigkeit.
- **Frist Zugriffsprotokoll** (DS-07): Vorschlag 30 Tage.
- **Help-Kontaktliste über das Portal pflegen** (A15, «wer genau pflegt» offen): noch nicht in der Schnittstelle, weiter über `contacts_cli.py`.
- **Medikamente:** ohne Vorerinnerung als Standard (Vorschlag aus PR 4, nicht bestätigt).
