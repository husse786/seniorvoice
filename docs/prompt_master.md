# SeniorVoice — Master Prompt
**Initialisierungs-Prompt für jede Coding-Session**

> **Anleitung:** Diesen Prompt am Anfang jeder neuen Claude-Session in Antigravity einfügen.  
> Claude liest die Projektdateien und weiss sofort wo wir stehen — kein Re-Explaining nötig.

---

## Prompt (kopieren & einfügen)

```
Du bist der Coding-Assistent für das Projekt SeniorVoice.

Lies zuerst folgende Dateien im Repo vollständig durch, bevor du irgendetwas tust:
1. docs/projektantrag.md        — Projektkontext, Architektur, Tech Stack, Scope
2. docs/arbeitsprotokoll.md     — Was bisher gemacht wurde, getroffene Entscheide, bekannte Probleme
3. docs/workpackages.md         — Alle Arbeitspakete mit aktuellem Status (⬜ offen / 🔄 in Bearbeitung / ✅ erledigt)

Sobald du alle drei Dateien gelesen hast:
1. Fasse in 3–5 Sätzen zusammen was du verstanden hast (Projekt, aktueller Stand, nächster Schritt)
2. Identifiziere das nächste offene Arbeitspaket (⬜) aus workpackages.md
3. Frage mich ob wir mit diesem Paket starten sollen, oder ob ich etwas anderes priorisieren will
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
- Sag mir welches Arbeitspaket wir erledigt haben (A-XX)
- Ich aktualisiere workpackages.md (✅ + Datum + Autor)
- Dann fahren wir mit dem nächsten Paket fort
```

---

## Kurzversion (für Folge-Sessions)

Wenn der Kontext bereits bekannt ist und du nur weitermachen willst:

```
Lies docs/workpackages.md und zeig mir den aktuellen Stand.
Was ist das nächste offene Arbeitspaket?
```

---

## Hinweise für das Team

**Wer kann diesen Prompt verwenden?**  
Alle Teammitglieder — Yanick, Chris, Sansone, Haris. Jeder kann eine Session starten und am aktuellen Stand weiterarbeiten.

**Was tun nach einer Session?**
1. `docs/workpackages.md` aktualisieren — erledigte Pakete mit ✅, Datum und deinem Namen
2. `docs/arbeitsprotokoll.md` — neuen Eintrag hinzufügen (Claude hilft dabei mit dem Projektdokumentation-Skill)
3. Änderungen committen und pushen:
```bash
git add .
git commit -m "feat: [kurze Beschreibung was gemacht wurde]"
git push
```

**Branching:**
- `main` — stabiler Stand, nur via PR
- `dev` — aktiver Entwicklungszweig
- `feature/[service-name]` — pro Service ein Branch (z.B. `feature/stt-service`)

**Commit-Konvention:**
| Prefix | Wann |
|---|---|
| `feat:` | Neue Funktionalität |
| `fix:` | Bugfix |
| `chore:` | Setup, Konfig, Doku |
| `test:` | Tests hinzufügen |
| `refactor:` | Code umstrukturieren ohne Funktionsänderung |

---

*Letzte Aktualisierung: 20.03.2026 | Yanick*
