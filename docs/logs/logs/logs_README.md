# Work Logs — SeniorVoice

Dieses Verzeichnis enthält alle technischen Arbeitsprotokoll-Einträge des Projekts SeniorVoice.

**Konvention:** Pro Session eine Datei — nach jeder Coding-Session wird ein neuer Eintrag erstellt.  
**Dateiname:** `[ID]_log_[DDMMYYYY].md` — z.B. `002_log_21032026.md`  
**Screenshots:** Ablage in `logs/screenshots/` — Einbettung via Markdown (siehe unten)

---

## Log-Übersicht

| Log ID | Woche | Inhalt | Datum | Autor |
|---|---|---|---|---|
| [001](001_log_20032026.md) | W05 | Pi Setup, Security Hardening & Repo Setup | 20.03.2026 | Yanick |

---

## Neuen Log-Eintrag erstellen

Am Ende jeder Coding-Session — egal ob gross oder klein — wird ein Log-Eintrag erstellt. Dafür gibt es den **Projektdokumentation-Skill** in Claude, der den Eintrag automatisch im richtigen Format generiert.

### Schritt 1 — Claude öffnen und Skill verwenden

Öffne Claude (claude.ai oder Antigravity) und schreibe:

```
Schreibe einen Work-Log-Eintrag für folgende Arbeit:

Log-ID: [nächste freie Nummer, z.B. 002]
Autor: [Dein Name]
Projektwoche: [z.B. W06]
Datum: [TT.MM.JJJJ]
Dauer: [z.B. 2 Stunden]
Action-IDs (RAID): [z.B. A-07, A-08]
GitHub Referenz: [z.B. feat/stt-service / commit abc1234 oder —]

WAS WURDE GEMACHT:
[Deine Notizen — Stichworte reichen]

TECHNISCHE ENTSCHEIDE:
[z.B. "faster-whisper small gewählt wegen Latenz auf Pi"]

PROBLEME / LEARNINGS:
[z.B. "Docker Build dauerte lange — BuildKit aktiviert"]

SCREENSHOTS:
[z.B. "Terminal-Output /transcribe Endpoint"]
```

Der Skill generiert automatisch:
- Den vollständigen Log-Eintrag im richtigen Format
- Die fertige Tabellenzeile für diese README

### Schritt 2 — Datei anlegen

Neue Datei erstellen: `logs/[ID]_log_[DDMMYYYY].md`  
Generierten Inhalt von Claude hineinkopieren.

### Schritt 3 — Screenshots hinzufügen (falls vorhanden)

Screenshots in `logs/screenshots/` ablegen und im Log verlinken (siehe Abschnitt unten).

### Schritt 4 — README aktualisieren

Die von Claude generierte Tabellenzeile oben in die Log-Übersicht einfügen.

### Schritt 5 — Committen

```bash
git add .
git commit -m "chore: add log [ID]"
git push
```

---

## Screenshots einbetten

**Ablageort:** `logs/screenshots/`  
**Namenskonvention:** `[log-id]_[kurzbeschreibung].png` — z.B. `001_ufw_status.png`

**Markdown-Code zum Einbetten:**

```markdown
![Beschreibung](screenshots/001_ufw_status.png)
```

**Beispiel mit Bildunterschrift:**

![UFW, Docker Hello World, Ollama Version](screenshots/001_ufw_status.docker_hello_world.png)

Auf Mac: Screenshot mit `Cmd + Shift + 4` erstellen → in `logs/screenshots/` ablegen → im Log referenzieren.