# Grafana (Technik-Analyse im Team)

Grafana zeigt die Messwerte eines Geräts als Diagramme: Modell-Benchmarks (Tokens pro Sekunde, Zeit bis zum ersten Token) und die Zeiten jeder Gesprächsrunde. Die Diagramme stammen von der FS26-Gruppe (`dashboard.json`, Protokoll 011 vom 03.05.2026) und laufen unverändert weiter.

## Was sich gegenüber FS26 ändert

| FS26 | HS26 | Grund |
|---|---|---|
| Grafana las `seniorvoice.db`, dieselbe Datei wie die Notizen über die Seniorin | Messwerte liegen in **`metrics.db`**; Grafana bekommt nur diese Datei | Grafana soll keine Senioren-Daten lesen können (A8, B5) |
| Zugriff per SSH-Tunnel | nur auf dem Gerät oder über WireGuard (OA-09) | Gerät nicht im Internet erreichbar |
| Dauerbetrieb | Werkzeug für Entwicklung und Tests | Einzelne Gesprächszeiten zeigen den Tagesablauf; im Betrieb ist Grafana aus, die Portal-Ansicht «Technik» zeigt nur Tageswerte |

## Einrichten

1. Grafana und das SQLite-Plugin `frser-sqlite-datasource` installieren (wie FS26).
2. Datenquelle: Pfad `~/seniorvoice/metrics.db` (bzw. `METRICS_DB_PATH`). **Nie** `seniorvoice.db` eintragen. Grafana braucht auf die Datei nur Leserechte.
3. In `grafana.ini` Grafana nur lokal oder auf der WireGuard-Adresse lauschen lassen:
   ```ini
   [server]
   http_addr = 127.0.0.1
   ```
4. `dashboard_import.json` importieren.

Alte Messwerte aus FS26-Zeiten in `seniorvoice.db` werden nicht übernommen; neue Werte entstehen ab dem ersten Start mit dieser Version. Messwerte werden nach 30 Tagen gelöscht (Vorschlag, `metrics.METRICS_RETENTION_DAYS`).
