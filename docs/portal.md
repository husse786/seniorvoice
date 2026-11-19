# Portal (Z7)

Status: Entwurf. Die ganze Kette ist in der Cloud-Testumgebung durchgespielt: Termin im Portal eingetragen, simuliertes Telefon klingelt zur Minute, Abheben, im Portal steht «bestätigt». Auf einem Mac noch nicht geprüft.

## Was das Portal ist

Eine Web-Seite für Angehörige, Spitex und das Projektteam. Es läuft auf dem **Team-Laptop** und holt alles **live vom Gerät** (B4). Gespeichert wird im Portal nur das Verzeichnis (D16): Konten, Rollen, Zuordnungen, Gerätetoken und die Anmeldungen der letzten 30 Tage. Termine, Hilfe-Verlauf und Rat-Infos liegen nur auf dem Gerät.

| Rolle | sieht |
|---|---|
| Angehörige | genau ein Gerät: Termine (eintragen, eigene löschen, Status), Hilfe-Verlauf (wenn am Gerät freigegeben), Rat-Infos, eigene Zugriffe |
| Spitex | mehrere zugeordnete Geräte, sonst wie Angehörige |
| Admin | alle Geräte, **nur Technik** (B5): Zustand, Sprachmodell, Antwortzeiten, Fehler, Zugriffsprotokoll, Anmeldungen am Portal |

Rechte werden zweimal geprüft: im Portal (Rolle und Zuordnung) und am Gerät (eigene Freigabeliste, `device_api_cli.py grant`). Ohne Freigabe am Gerät sieht auch ein Portal-Konto nichts.

Anmeldung mit Passwort **und** 6-stelligem Code aus einer Authenticator-App (z.B. Google Authenticator, Microsoft Authenticator, 1Password). Nach 5 Fehlversuchen ist das Konto 5 Minuten gesperrt. Die Sitzung liegt nur im Arbeitsspeicher und endet nach 30 Minuten ohne Aktivität.

## Demo auf einem Rechner (Mac)

Voraussetzung: das simulierte Gerät ist eingerichtet (`docs/simulation.md`, Schritte 1 bis 6). Der dort erzeugte Gerätetoken wird hier gebraucht.

1. Konten anlegen. Der Login muss **gleich** heissen wie die Freigabe am Gerät (Schritt 5 in `docs/simulation.md`):
   ```bash
   cd portal
   python portal_cli.py add-account sandra.keller "Sandra Keller" angehoerige
   python portal_cli.py add-account admin.team "Projektteam" admin
   ```
   Jeweils wird ein Passwort abgefragt und ein Link `otpauth://…` ausgegeben. Diesen Link (oder den Schlüssel) in der Authenticator-App auf dem Handy eintragen.
2. Gerät eintragen und zuordnen (der Token wird abgefragt):
   ```bash
   python portal_cli.py add-device keller "Telefon Frau Keller" "Frau Keller" http://127.0.0.1:8770
   python portal_cli.py assign sandra.keller keller
   python portal_cli.py list
   ```
3. Alles starten:
   ```bash
   scripts/start-demo.sh                   # Portal + simuliertes Gerät
   SIM_AUDIO=text scripts/start-demo.sh    # dasselbe im Textmodus
   ```
4. Zwei Browserfenster nebeneinander: Portal `http://127.0.0.1:8780`, Telefon `http://127.0.0.1:8771`.

Ablauf für die Präsentation: siehe «Demo-Ablauf» in `docs/simulation.md`. Das Portal aktualisiert Termine, Hilfe-Verlauf und Technik alle 15 Sekunden von selbst.

Das Verzeichnis liegt standardmässig in `~/seniorvoice-portal/portal.db` (nur für den eigenen Benutzer lesbar, weil es die Gerätetoken enthält). Anderer Ort: `PORTAL_DB=… scripts/start-portal.sh`.

## Mit dem echten Gerät (Pi 5)

Das Portal bleibt auf dem Laptop. Der Pi verbindet sich per WireGuard mit dem Laptop; das Gerät wird mit seiner Tunnel-Adresse eingetragen statt `127.0.0.1`:

```bash
python portal_cli.py add-device keller "Telefon Frau Keller" "Frau Keller" http://10.77.0.2:8770
```

Einrichtung des Tunnels: `docs/wireguard.md`.

## Einstellungen

| Variable | Standard | Bedeutung |
|---|---|---|
| `PORTAL_HOST` | `127.0.0.1` | Adresse, auf der das Portal hört. Nie `0.0.0.0` (wird abgelehnt). |
| `PORTAL_PORT` | `8780` | |
| `PORTAL_DB` | `~/seniorvoice-portal/portal.db` | Verzeichnis (D16) |
| `PORTAL_ALLOWED_HOSTS` | leer | weitere Hostnamen, unter denen das Portal aufgerufen wird |
| `PORTAL_SECURE_COOKIE` | `false` | auf `true`, sobald das Portal hinter HTTPS läuft (Produktivbetrieb) |
| `PORTAL_SESSION_IDLE` | `1800` | Sekunden ohne Aktivität bis zur Abmeldung |

Optional in `portal/.env`; `scripts/start-portal.sh` liest die Datei.

## Grenzen (bewusst)

- Kein Konto-Verwaltung im Browser: Konten und Geräte nur über `portal_cli.py` auf dem Laptop.
- Keine Bearbeitung bestehender Termine im Browser (die Geräte-API kann es; Löschen und neu Eintragen genügt für die Tests).
- Help-Kette (Reihenfolge der Kontakte) wird noch am Gerät mit `contacts_cli.py` gepflegt, nicht im Portal.
- Kein HTTPS auf dem Laptop: Der Verkehr zum Gerät läuft im WireGuard-Tunnel, der Browser greift lokal zu. Für den Produktivbetrieb siehe `docs/wireguard.md`, Abschnitt «Produktivbetrieb».
