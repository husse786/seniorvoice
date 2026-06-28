# SeniorVoice — Master Prompt
**Initialisierungs-Prompt für jede Coding-Session**

> **Anleitung:** Diesen Prompt am Anfang jeder neuen Claude-Session in Antigravity einfügen.  
> Claude liest die Projektdateien und weiss sofort wo wir stehen — kein Re-Explaining nötig.

---

## Prompt (kopieren & einfügen)

```
Du bist der Coding-Assistent für das Projekt SeniorVoice.

Lies zuerst folgende Dateien im Repo vollständig durch, bevor du irgendetwas tust:
1. docs/projektantrag.md      — Projektkontext, Architektur, Tech Stack, Scope
2. docs/current_state.md      — Aktueller Stand, nächster Schritt, offene Blocker
3. docs/workpackages.md       — Alle Arbeitspakete mit Status (⬜ offen / 🔄 in Bearbeitung / ✅ erledigt)

Sobald du alle drei Dateien gelesen hast:
1. Fasse in 3–5 Sätzen zusammen was du verstanden hast (Projekt, aktueller Stand, nächster Schritt)
2. Nenne das nächste offene Arbeitspaket (⬜) aus current_state.md / workpackages.md
3. Frage mich ob wir damit starten sollen, oder ob ich etwas anderes priorisieren will
4. Warte auf meine Bestätigung — dann starte mit der Implementierung

Beim Coden gelten folgende Regeln:
- Sprache: Python 3.11
- Framework: FastAPI + uvicorn
- Alle Configs via .env (keine hardcodierten Werte)
- Pydantic Models für alle Request/Response Schemas
- /health Endpoint auf jedem Service
- arm64-kompatible Docker Base Images (Raspberry Pi 5)
- Strukturiertes JSON Logging
- Einen File nach dem anderen — erkläre jeden Entscheid kurz
- Frage bevor du Annahmen triffst bei Modellnamen, Ports, Pfaden

Nach jeder abgeschlossenen Aufgabe:
- Nenne das erledigte Arbeitspaket (A-XX)
- Ich aktualisiere docs/workpackages.md (✅ + Datum + Autor)
- Ich aktualisiere docs/current_state.md (neuer Stand, nächster Schritt)
- Dann fahren wir mit dem nächsten Paket fort
```

---

## Kurzversion (für Folge-Sessions)

Wenn du schnell weitermachen willst ohne langen Kontext-Aufbau:

```
Lies docs/current_state.md — was ist der nächste Schritt?
```

---

## Hinweise für das Team

**Wer kann diesen Prompt verwenden?**  
Alle Teammitglieder — Yanick, Teammitglied 3, Teammitglied 1, Teammitglied 2. Jeder kann eine Session starten und am aktuellen Stand weiterarbeiten.

**Was tun nach einer Session?**

1. `docs/workpackages.md` aktualisieren — erledigte Pakete mit ✅, Datum und Name
2. `docs/current_state.md` aktualisieren — Stand, nächster Schritt, Blocker überschreiben
3. Log-Eintrag erstellen mit dem Projektdokumentation-Skill (Anleitung: `logs/README.md`)
4. Committen und pushen:

```bash
git add .
git commit -m "feat: [kurze Beschreibung]"
git push
```

**Branching:**
| Branch | Zweck |
|---|---|
| `main` | Stabiler Stand — nur via Pull Request |
| `dev` | Aktiver Entwicklungszweig |
| `feature/[service-name]` | Pro Service (z.B. `feature/stt-service`) |

**Commit-Konvention:**
| Prefix | Wann |
|---|---|
| `feat:` | Neue Funktionalität |
| `fix:` | Bugfix |
| `chore:` | Setup, Konfig, Dokumentation |
| `test:` | Tests hinzufügen |
| `refactor:` | Umstrukturierung ohne Funktionsänderung |

---

*Letzte Aktualisierung: 20.03.2026 | Yanick*
