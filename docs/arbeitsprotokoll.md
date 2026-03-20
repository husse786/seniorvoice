# Arbeitsprotokoll — SeniorVoice
**Projekt:** SeniorVoice — Lokaler KI-Sprachassistent für Senioren  
**Modul:** IoT Data Streaming & Analytics · ZHAW FS 2026  
**Team:** Yanick · Chris · Sansone · Haris  
**Protokollführung:** Yanick  

---

## Eintrag #001 · W05 · Raspberry Pi 5 Setup, Sicherheitskonfiguration & Docker-Installation

**Meta-Informationen**

| Feld | Wert |
|---|---|
| Datum | 19.–20.03.2026 |
| Projektwoche | W05 |
| Autor | Yanick |
| Dauer | ca. 4–5 Stunden |
| Action-IDs (RAID) | A-01 |
| GitHub Referenz | — |
| Status | Abgeschlossen (mit offenen Folgeschritten) |

---

**1 · Ziel dieses Schritts**

Gemäss Projektplan W05 (Modul 0 — Infrastruktur & Setup) wurde der Raspberry Pi 5 (16 GB) als Entwicklungsgerät in Betrieb genommen. Ziel war ein vollständig headless, remote-zugängliches und gehärtetes System als Grundlage für alle nachfolgenden Microservice-Entwicklungen. Docker und Ollama wurden vorinstalliert, um W06/W07 zu entlasten.

---

**2 · Durchgeführte Aktivitäten**

- Raspberry Pi 5 (16 GB) headless mit Raspberry Pi Imager aufgesetzt (SSH, WiFi CH, Europe/Zurich, Hostname `senioragent`)
- AI Hat+ physisch installiert (Evaluation für Whisper-Acceleration)
- Pi Connect eingerichtet und mit Yanick-Account verknüpft (Remote-Display-Zugriff)
- Netzwerksicherheit evaluiert und konfiguriert:
  - Guest-WiFi-Isolation versucht → Salt Fiber Box unterstützt kein Port-Forwarding auf Guest-Subnet (`192.168.254.x`) → Pi zurück auf Haupt-LAN (`192.168.1.36`)
  - IPv6-only Anschluss bei Salt bestätigt → kein externer SSH via Port-Forwarding möglich
  - UFW aktiviert: Default deny incoming, Port 22 TCP erlaubt
  - Docker UFW-Bypass deaktiviert (`"iptables": false` in `/etc/docker/daemon.json`)
- Benutzerverwaltung gehärtet:
  - Benutzer `yanick`, `sansone`, `haris`, `chris` erstellt (alle mit sudo)
  - Default-User `admin` gesperrt (`passwd -l admin`)
  - `PermitRootLogin no` in `/etc/ssh/sshd_config` gesetzt
- SSH Key-Auth für `yanick` eingerichtet und getestet (`192.168.1.36`)
- Locale-Fehler behoben (`en_GB.UTF-8`)
- Docker Engine 29.3.0 installiert (via `get.docker.com`)
  - Alle 4 Benutzer zur `docker`-Gruppe hinzugefügt
  - `hello-world` Container erfolgreich ausgeführt (arm64)
- Ollama 0.18.2 installiert (via `ollama.com/install.sh`)
  - Läuft on-demand via `ollama serve &` (kein systemd-Service — ressourcenschonend)
  - Gebunden an `127.0.0.1:11434` — nicht öffentlich erreichbar
- GitHub Repository erstellt: https://github.com/yanickfischer/seniorvoice.git
- Repo-Struktur angelegt: `services/`, `data/sqlite/`, `data/grafana/`
- `.venv` eingerichtet, `.gitignore` konfiguriert
- SSH-Zugriffsguide für Team erstellt (`docs/ssh_access_guide.md`)

---

**3 · Technische Entscheide**

| Entscheid | Begründung | Verknüpfung RAID |
|---|---|---|
| Pi bleibt auf Haupt-LAN statt Guest-WiFi | Salt Fiber Box unterstützt kein Port-Forwarding auf Guest-Subnet; UFW + Key-Auth bieten ausreichende Härtung für Entwicklungsphase | D-01 |
| Kein systemd-Service für Ollama | On-demand Start spart RAM beim Boot; Pi 5 Ressourcen für Docker-Services reserviert | D-02 |
| Docker `iptables: false` | Docker umgeht standardmässig UFW — kritische Härtung vor erstem Container-Deployment | D-03 |
| SSH-Zugang für externes Team via Universität IoT-Netz | Salt liefert IPv6-only → kein externer SSH möglich; Uni-Netz mit Prof. klären | D-04 |
| Venv statt globale Python-Installation | Saubere Abhängigkeitsisolation pro Projekt; keine Konflikte mit Base-Distribution | D-05 |

---

**4 · Probleme & Lösungen**

| Problem | Lösung / Workaround | Issue-ID (RAID) |
|---|---|---|
| `127.0.1.1` als Pi-IP angezeigt | Loopback-Adresse aus `/etc/hosts` — echte IP via `ip addr show wlan0` ermittelt | — |
| Guest-WiFi Port-Forwarding schlägt fehl | Salt Fiber Box lehnt `192.168.254.x` als internes Ziel ab — Pi zurück auf Haupt-LAN | I-01 |
| Salt liefert IPv6-only (`2a02:...`) | Kein IPv4 für Port-Forwarding verfügbar — externer SSH-Zugang blockiert | I-02 |
| Ollama systemd-Service nicht erstellt | Install-Script erstellt keinen Service — manueller Start via `ollama serve &` | — |
| SSH-Befehlskette auf einmal eingefügt | Shell interpretierte mehrere Befehle als eine Zeile — Befehle einzeln ausgeführt | — |
| Locale-Warnung beim SSH-Login | `sudo update-locale LC_ALL=en_GB.UTF-8` — nur `en_GB` auf diesem Image verfügbar | — |
| Docker-Installation dauerte 20+ Minuten | Pi WiFi-Modul langsam bei grossen Downloads — Ethernet für künftige Downloads empfohlen | — |

---

**5 · Ergebnis / Lieferobjekte**

- Raspberry Pi 5 headless, SSH-zugänglich auf `192.168.1.36`
- 4 Benutzerkonten angelegt (`yanick`, `sansone`, `haris`, `chris`), `admin` gesperrt, Root-Login deaktiviert
- UFW aktiv, Docker UFW-Bypass behoben (`iptables: false`)
- Docker Engine 29.3.0 lauffähig (arm64), `hello-world` verifiziert
- Ollama 0.18.2 installiert, on-demand startbar, lokal gebunden an `127.0.0.1:11434`
- GitHub Repo erstellt mit Ordnerstruktur für alle 5 Services
- `.venv` + `.gitignore` konfiguriert
- SSH-Zugriffsguide für Team: `docs/ssh_access_guide.md`

---

**6 · Nächste Schritte**

- `docker-compose.yml` Skeleton für alle 5 Services aufsetzen (A-02)
- Branching-Strategie definieren und dokumentieren (A-03)
- `llama3.2:3b` auf Pi pullen und Antwortzeit messen (A-04)
- SSH-Zugang für Sansone, Haris, Chris einrichten — public keys einsammeln (A-05)
- Externer SSH-Zugang via Universität IoT-Netz mit Prof. klären (A-06)
- stt-service Skeleton implementieren (W06 Start)

---

**7 · Screenshots / Anhänge**

> [ Screenshot: `sudo ufw status` — UFW aktiv, Port 22 offen ]
> [ Screenshot: `docker run hello-world` — arm64 Container läuft ]
> [ Screenshot: Ollama `serve` Output — gebunden an `127.0.0.1:11434` ]
> [ Screenshot: `ls services/` — Repo-Struktur angelegt ]

---

*Letzte Aktualisierung: 20.03.2026 | Yanick*
