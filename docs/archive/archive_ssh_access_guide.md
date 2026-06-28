# SSH Access Guide — SeniorVoice Raspberry Pi

**Projekt:** SeniorVoice | ZHAW IoT Data Modul  
**Maintainer:** Yanick  
**Pi IP (Heimnetz):** `<PI_IP>`  
**Hostname:** `senioragent`

---

## Wichtig: Aktueller Zugangsstand

| Zugangsweg | Status | Bemerkung |
|---|---|---|
| SSH im Heimnetz (LAN) | ✅ Funktioniert | Pi und Laptop müssen im gleichen WiFi sein |
| SSH remote (von aussen) | ❌ Nicht verfügbar | Salt liefert IPv6-only — Port-Forwarding nicht möglich |
| Pi Connect (Remote-Display) | ✅ Funktioniert | Nur Yanick-Account; für alle anderen kein Zugang |
| SSH via Uni IoT-Netz | ⏳ In Klärung | Prof. Weber kontaktieren — MAC-Adresse des Pi registrieren |

> **Für Teammitglieder:** Bis der Uni-Zugang geklärt ist, ist SSH nur möglich wenn ihr im gleichen Netzwerk wie der Pi seid (Yanicks Heimnetz oder Uni IoT-Netz sobald verfügbar).

---

## Voraussetzungen

Bevor du dich verbinden kannst, braucht Yanick deinen **öffentlichen SSH-Schlüssel**. Folge Step 1, sende Yanick den Key, und warte auf seine Bestätigung.

---

## Step 1 — SSH Key Pair generieren (einmalig, auf deinem Laptop)

Öffne ein Terminal:
- **Mac/Linux:** Terminal
- **Windows:** PowerShell oder Windows Terminal

```bash
ssh-keygen -t ed25519 -C "deinname@seniorvoice"
```

- **Enter** drücken für Standard-Speicherort (`~/.ssh/id_ed25519`)
- Passphrase optional — leer lassen und Enter drücken ist OK

Zwei Dateien werden erstellt:
- `~/.ssh/id_ed25519` → dein **privater Schlüssel** — niemals teilen, niemals senden
- `~/.ssh/id_ed25519.pub` → dein **öffentlicher Schlüssel** — diesen an Yanick senden

**Öffentlichen Key ausgeben und an Yanick senden:**

```bash
cat ~/.ssh/id_ed25519.pub
```

Die Ausgabe sieht so aus — die gesamte Zeile kopieren:
```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA... deinname@seniorvoice
```

Den Key via **MS Teams** an Yanick schicken.

---

## Step 2 — Warten bis Yanick deinen Key hinzugefügt hat

Yanick führt für jeden Teamkollegen folgende Befehle aus (einzeln, einen nach dem anderen):

```bash
sudo su - username
```
```bash
mkdir -p ~/.ssh
```
```bash
chmod 700 ~/.ssh
```
```bash
echo "PASTE_PUBLIC_KEY_HERE" >> ~/.ssh/authorized_keys
```
```bash
chmod 600 ~/.ssh/authorized_keys
```
```bash
exit
```

Du erhältst eine Bestätigung via Teams sobald dein Key hinzugefügt wurde.

---

## Step 3 — SSH Verbindung herstellen

### Option A: Im Heimnetz (Yanicks WiFi)

```bash
ssh username@<PI_IP>
```

| Teammitglied | Befehl |
|---|---|
| Yanick | `ssh yanick@<PI_IP>` |
| Teammitglied 1 | `ssh user1@<PI_IP>` |
| Teammitglied 2 | `ssh user2@<PI_IP>` |
| Teammitglied 3 | `ssh user3@<PI_IP>` |

**Erster Login:** dein Laptop fragt einmalig nach Bestätigung des Fingerprints — `yes` eingeben und Enter drücken:

```
The authenticity of host '<PI_IP>' can't be established.
ED25519 key fingerprint is SHA256:...
Are you sure you want to continue connecting (yes/no)? yes
```

### Option B: Via Uni IoT-Netz (sobald verfügbar)

Sobald der Pi im Uni IoT-Netz registriert ist, wird eine neue IP vergeben. Yanick kommuniziert die neue IP und aktualisiert diesen Guide.

---

## Troubleshooting

| Problem | Lösung |
|---|---|
| `Permission denied (publickey)` | Key noch nicht hinzugefügt — Yanick kontaktieren |
| `Connection refused` | Pi ist offline oder SSH läuft nicht — Yanick kontaktieren |
| `Connection timed out` | Du bist nicht im gleichen Netzwerk wie der Pi |
| `WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED` | Pi wurde neu aufgesetzt — `ssh-keygen -R <PI_IP>` ausführen und nochmals verbinden |
| Password-Prompt erscheint | Key-Auth noch nicht aktiv — temporäres Passwort von Yanick verwenden |

---

## Checkliste erster Login

- [ ] Key Pair generiert (`ssh-keygen`)
- [ ] Öffentlichen Key (`cat ~/.ssh/id_ed25519.pub`) via Teams an Yanick gesendet
- [ ] Bestätigung von Yanick erhalten
- [ ] Erfolgreich verbunden: `ssh username@<PI_IP>`
- [ ] Temporäres Passwort geändert: `passwd`

---

## Sicherheitshinweise

- **Privaten Key niemals teilen** (`~/.ssh/id_ed25519`) — bleibt auf deinem Laptop
- Jedes Teammitglied hat einen eigenen Account — keine geteilten Credentials
- Default-User `admin` ist deaktiviert
- Passwort-Login wird deaktiviert sobald alle Keys eingerichtet sind

---

*Letzte Aktualisierung: 20.03.2026 | Yanick*
