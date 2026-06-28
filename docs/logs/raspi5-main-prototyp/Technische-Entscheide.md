## Technische Entscheide (D-Register)

| ID | Entscheid | Begründung |
|---|---|---|
| D-01 | Pi auf Haupt-LAN statt Guest-WiFi | Salt Router unterstützt kein Port-Forwarding auf Guest-Subnet |
| D-02 | Ollama on-demand statt systemd | RAM sparen für Docker |
| D-03 | Docker `iptables: false` | Docker umgeht UFW standardmässig |
| D-04 | lgpio statt gpiozero | Pi 5 RP1-Chip erfordert explizite gpiochip4-Adressierung |
| D-05 | Python venv statt global | Saubere Dependency-Isolation |
| D-06 | Monolithische Pipeline statt Docker-Microservices (MVP) | Schnellerer Weg zum Prototyp; Microservice-Split nach Validierung |
| D-07 | Moonshot Kimi API direkt statt OpenClaw | OpenClaw nicht mehr installiert; direkter Call simpler |
| D-08 | BT-Speaker (Sony SRS-XB23) | Kein kabelgebundener Speaker verfügbar |
| D-09 | Sense HAT nicht montiert | GPIO-Pins für PIR-Sensor benötigt |
| D-10 | PIR auf GPIO4 statt GPIO17 | Physische Verdrahtung; config.py Default angepasst |
| D-11 | venv mit `--system-site-packages` | lgpio nur system-weit verfügbar (kein pip wheel auf arm64) |
| D-12 | In-Memory Session History mit 5-Min-Timeout | Einfachste Multi-Turn-Lösung; Timeout deckt typische Interaktionsdauer |
| D-13 | SQLite für Long-Term Memory | Stdlib, schnell auf NVMe, Schema erweiterbar für Grafana/Logging |
| D-14 | Separate LLM-Funktion für Faktenextraktion | chat() verwaltet History; Extraktion braucht eigenen Prompt |
| D-15 | Async Faktenextraktion in Daemon-Thread | Benutzer wartet nicht; bei Shutdown synchroner Call |
| D-16 | LLM_API_KEY optional (kein hard-fail) | Ermöglicht lokales Ollama ohne API-Key |
| D-17 | Audio-Feedback via numpy-generierte Töne | Keine externen Sound-Dateien nötig; pitch/dauer leicht anpassbar |
| D-18 | Python logging statt print() | Structured logs mit Rotation; Grundlage für Grafana-Dashboard |
| D-19 | Interaction-Timing in gleicher SQLite-DB | Wiederverwendung der Memory-DB; eine Datenquelle für Grafana |
| D-20 | `llm_backend.py` als LLM-Abstraktionsschicht | Minimale Änderung; kein Klassen-Overhead; `complete()` + `stream()` Interface |
| D-21 | `LLM_BACKENDS=ollama,kimi` Env-Var für Fallback-Reihenfolge | Config-driven, zero-breaking-change (default = bestehendes Verhalten) |
| D-22 | Named Backend Config via `LLM_{NAME}_*` Env-Vars | Folgt bestehendem Env-Var-Muster; keine Config-Files nötig |
| D-23 | Streaming via urllib SSE Line-Iteration | Keine neuen Dependencies; Ollama nutzt Standard-SSE-Format |
| D-24 | Sequentielles per-sentence TTS (kein Threading) | speak() ist blocking + gleicher WAV-Pfad; sequential ist sicher |
| D-25 | Fallback nur bei Connection-Fehler, nicht mid-stream | Sobald Tokens fliessen, committen wir zum Backend |
| D-26 | gemma3:4b als lokaler Primary-LLM | Beste Deutsche Qualität im Benchmark (2.5 tok/s); qwen2.5:3b disqualifiziert wegen schlechtem Deutsch |
| D-27 | gemma3:1b als neuer Primary-Kandidat | 3.8 tok/s + 1.3s TTFT; mit Streaming bessere UX als Kimi Cloud (11.7s TTFT) |
| D-28 | Kimi Cloud nicht als Primary | Avg TTFT 11.7s (max 32.7s); User wartet zu lange auf erste Antwort |
| D-29 | gemma4-Serie disqualifiziert | "Thinking Models" mit 82–175s TTFT warm; für Voice-Assistant unbenutzbar |
| D-30 | `DB_PATH` als separater Env-Var für Benchmark-DB | Ermöglicht separate DB; Default = gleiche `seniorvoice.db` |
| D-31 | `model_variant` als Text-Feld statt Boolean | Flexibel für stock/tuned/quantized/etc. |
| D-32 | `--variant` als globaler CLI-Flag pro Invocation | Minimum-Complexity; separate Runs für unterschiedliche Tags |
| D-33 | Best-effort DB-Writes in Benchmark | DB-Fehler dürfen Messung nicht stören |
| D-34 | systemd oneshot-Unit für CPU Governor `performance` | Standardisiert, `systemctl disable` zum Revert |
| D-35 | `num_ctx 512` für getunte Modellvarianten | KV-Cache-Reduktion; Voice-Assistant braucht max ~512 Tokens |
| D-36 | LFM2.5-350M als Q8_0 (Ollama-Default) | 379 MB; bei 354M Params kein Grund für stärkere Quantisierung |
| D-37 | `num_thread=3` als optimaler Wert | Pi 5 hat 4 Cores — bei 4 Threads Thread-Contention; 3 Threads = +118% |
| D-38 | `gemma3:1b-prod` als Produktionsmodell | num_thread=3, num_ctx=512, num_batch=128 — alle optimalen Parameter kombiniert |
| D-39 | LFM2.5-350M verworfen | Deutsche Sprachqualität unbrauchbar für Senioren-Zielgruppe |
| D-40 | Overclock 2.8 GHz als Produktionseinstellung | +32% tok/s bei moderatem Voltage; 3.0 GHz nur +3% mehr bei doppeltem Voltage |
| D-41 | `config.txt.bak` Backup vor Overclock | Schnelles Revert bei Instabilität |
| D-42 | `ProtectHome=false` systemd-Override für Grafana | Default blockiert Zugriff auf SQLite unter `/home/` |
| D-43 | `queryType: "table"` + Transformationen statt `"time series"` | Plugin v4.0.2 Time-Series-Modus broken |
| D-44 | SSH-Tunnel für Grafana-Zugriff | Pi auf VLAN/Switch, Mac auf WiFi — kein direktes Routing |
| D-45 | Bar-Chart Labels -45° rotiert | Modellnamen überlappen bei horizontaler Darstellung |
| D-46 | Dashboard JSON versioniert in `docs/grafana/` | Reproduzierbarer Import via API |
| D-47 | num_ctx von 512 auf 1024/2048 für Faktenretention | 512 Tokens reichen nicht für System-Prompt + Fakten + History über mehrere Turns |
| D-48 | Facts Re-Injection vor User-Nachricht | Defense-in-Depth: Small Models verlieren frühen Kontext bei wachsender History |
| D-49 | LLM-Warmup bei Pipeline-Start | Ollama entlädt Modelle nach 5 Min; Warmup eliminiert Cold-Start |
| D-50 | Drei num_ctx-Varianten (512/1024/2048) | A/B-Vergleich und schnelles Rollback ohne Modell-Rebuild |