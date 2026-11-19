"""Screen on the device (T11: 7" display, display only, no touch).

One page for the Raspberry Pi display in full screen and for the display
drawn into the simulated telephone (sim_phone.py shows the same page in a
frame). It shows:

- at rest: clock, date, today's appointments and medication, tomorrow's first
  appointment
- ringing: the reminder in large letters
- during a call: the last sentences (device and senior), large
- Help: who was told and that an answer is awaited (A13)

The conversation lives in RAM only and is cleared when the handset is hung
up (A8). Nothing is written to a file or a log. The page itself refreshes
once a second; the clock runs in the browser in Swiss time.

The screen server listens on 127.0.0.1 only (the Pi's own browser in kiosk
mode). Python standard library only.
"""

import collections
import json
import threading
import time
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
from zoneinfo import ZoneInfo

from logging_config import get_logger

log = get_logger("screen")

LOCAL_TZ = ZoneInfo("Europe/Zurich")
MAX_LINES = 4
MAX_TEXT = 400
AGENDA_CACHE_SECONDS = 15


def _hhmm(d: datetime) -> str:
    return d.strftime("%H:%M")


class Screen:
    """What the screen shows. Fed by the core; read by the page."""

    def __init__(self, phone_state: Callable[[], dict],
                 ringing_text: Callable[[], str | None] = lambda: None,
                 help_status: Callable[[], dict | None] = lambda: None,
                 now: Callable[[], datetime] = lambda: datetime.now(LOCAL_TZ),
                 monotonic: Callable[[], float] = time.monotonic):
        self.phone_state = phone_state
        self.ringing_text = ringing_text
        self.help_status = help_status
        self.now = now
        self.monotonic = monotonic
        self._lines: collections.deque = collections.deque(maxlen=MAX_LINES)
        self._lock = threading.Lock()
        self._agenda: tuple[float, str, dict] | None = None

    # --- conversation (RAM only) ---

    def show(self, text: str, output: str = "handset") -> None:
        """What the device said into the handset. Room speaker and the Help
        contact's messages are not part of the conversation."""
        if output == "handset":
            self._add("geraet", text)

    def heard(self, text: str) -> None:
        self._add("senior", text)

    def _add(self, who: str, text: str) -> None:
        text = " ".join(str(text).split())[:MAX_TEXT]
        if text:
            with self._lock:
                self._lines.append({"who": who, "text": text})

    def forget(self) -> None:
        with self._lock:
            self._lines.clear()

    # --- appointments of today (local DB, cached briefly) ---

    def agenda(self) -> dict:
        now = self.now().astimezone(LOCAL_TZ)
        day = now.date().isoformat()
        if self._agenda and self._agenda[1] == day and \
                self.monotonic() - self._agenda[0] < AGENDA_CACHE_SECONDS:
            data = self._agenda[2]
        else:
            data = self._read_agenda(now)
            self._agenda = (self.monotonic(), day, data)
        # "done" and "next" change with the clock, not with the database
        items, nxt = [], None
        for item in data["heute"]:
            done = item["at"] <= now
            if not done and nxt is None:
                nxt = item
            items.append({"zeit": _hhmm(item["at"]), "titel": item["titel"],
                          "art": item["art"], "vorbei": done, "naechster": False})
        if nxt is not None:
            items[data["heute"].index(nxt)]["naechster"] = True
        return {"heute": items, "morgen": data["morgen"]}

    @staticmethod
    def _read_agenda(now: datetime) -> dict:
        import appointments
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        try:
            today = appointments._between(start, start + timedelta(days=1), ("termin", "medikament"))
            tomorrow = appointments._between(start + timedelta(days=1), start + timedelta(days=2),
                                             ("termin",))
        except Exception as e:
            log.warning("Appointments not readable for the screen (%s)", type(e).__name__)
            return {"heute": [], "morgen": ""}
        return {"heute": [{"at": d, "titel": t, "art": k} for d, k, t in today],
                "morgen": f"{_hhmm(tomorrow[0][0])} {tomorrow[0][2]}" if tomorrow else ""}

    # --- everything the page needs ---

    def state(self) -> dict:
        phone = self.phone_state()
        help_status = (self.help_status()
                       if phone.get("help_open") or phone.get("help_phase") == "abgebrochen"
                       else None)
        ringing = bool(phone.get("ringing"))
        in_call = bool(phone.get("in_call"))
        if help_status is not None or phone.get("help_open"):
            mode = "hilfe"
        elif ringing:
            mode = "klingelt"
        elif in_call:
            mode = "gespraech"
        else:
            mode = "ruhe"
        reminder = ""
        if ringing:
            reminder = self.ringing_text() or ""
            for prefix in ("Guten Tag. ", "Guten Tag! "):
                if reminder.startswith(prefix):
                    reminder = reminder[len(prefix):]
        with self._lock:
            lines = list(self._lines) if in_call else []
        return {"modus": mode, "erinnerung": reminder, "gespraech": lines,
                "hilfe": help_status or {}, **self.agenda()}


# --- the page (shared with the simulated phone) -----------------------------

def send_page(handler: BaseHTTPRequestHandler, screen: Screen | None, path: str) -> bool:
    """Serve /screen and /screen/state. False if the path is not the screen's."""
    if path == "/screen":
        _send(handler, 200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        return True
    if path == "/screen/state":
        if screen is None:
            _send(handler, 404, b'{"error": "kein Bildschirm"}', "application/json")
        else:
            body = json.dumps(screen.state(), ensure_ascii=False).encode("utf-8")
            _send(handler, 200, body, "application/json; charset=utf-8")
        return True
    return False


def _send(handler, status: int, body: bytes, content_type: str) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    # Only the simulated phone page on the same address may show it in a frame
    handler.send_header("X-Frame-Options", "SAMEORIGIN")
    handler.send_header("Content-Security-Policy",
                        "default-src 'self'; style-src 'unsafe-inline'; "
                        "script-src 'unsafe-inline'; frame-ancestors 'self'")
    handler.end_headers()
    handler.wfile.write(body)


class ScreenServer:
    """The page for the Pi's own browser (kiosk mode), on 127.0.0.1 only."""

    def __init__(self, screen: Screen, port: int):
        self.screen = screen
        self.port = port
        self.server: ThreadingHTTPServer | None = None

    def start(self) -> None:
        screen = self.screen

        class Handler(BaseHTTPRequestHandler):
            server_version = "SeniorVoiceScreen"
            sys_version = ""

            def log_message(self, fmt, *args):
                pass

            def do_GET(self):
                host = self.headers.get("Host", "").rsplit(":", 1)[0].strip("[]")
                if host not in ("127.0.0.1", "localhost", "::1"):
                    return _send(self, 403, b'{"error": "forbidden"}', "application/json")
                path = "/screen" if self.path == "/" else self.path
                if not send_page(self, screen, path):
                    _send(self, 404, b'{"error": "not found"}', "application/json")

        self.server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, name="screen", daemon=True).start()
        log.info("Screen: http://127.0.0.1:%d", self.port)

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()


PAGE = """<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SeniorVoice – Bildschirm</title>
<style>
/* Sized in vw so the same page fills the 800x480 display and the small frame
   in the simulated phone. Single dark look: easy to read, no glare at night. */
:root{--bg:#0f1b24;--ink:#f3efe6;--muted:#9fb0bc;--card:#1b2a36;--hi:#ffd27a;--ok:#9be3b5;
--ring:#3a2a06;--help:#4a1410;color-scheme:dark}
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:var(--bg);color:var(--ink);overflow:hidden;cursor:none;
font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.view{position:absolute;inset:0;padding:4vw 5vw;display:flex;flex-direction:column;gap:2.2vw}
.view[hidden]{display:none}
.top{display:flex;justify-content:space-between;align-items:baseline;gap:2vw}
.clock{font-size:11vw;font-weight:700;line-height:1;font-variant-numeric:tabular-nums}
.date{font-size:3.8vw;color:var(--muted)}
.lbl{font-size:2.6vw;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
.items{display:flex;flex-direction:column;gap:1.4vw;overflow:hidden}
.item{background:var(--card);border-radius:1.6vw;padding:1.4vw 2.4vw;display:flex;gap:3vw;font-size:4.4vw;align-items:baseline}
.item b{font-variant-numeric:tabular-nums;min-width:12vw}
.item.next{outline:.4vw solid var(--hi)}.item.done{opacity:.5}
.empty{font-size:4.4vw;color:var(--muted)}
.foot{margin-top:auto;font-size:3vw;color:var(--muted)}
.big{font-size:6.4vw;font-weight:700;line-height:1.2}
.say{font-size:5.4vw;line-height:1.3}
.say .who{display:block;font-size:2.6vw;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
.say.me{color:var(--muted);font-size:4.2vw}
.ringv{background:var(--ring)}.ringv .big{color:var(--hi)}
.helpv{background:var(--help)}
.pill{background:#ffffff22;border-radius:99px;padding:.6vw 2vw;font-size:3.2vw}
.ok{color:var(--ok)}
.offline{position:absolute;right:2vw;bottom:1.5vw;font-size:2.4vw;color:var(--muted)}
</style></head><body>
<div class="view" id="ruhe">
  <div class="top"><div class="clock" data-clock></div><div class="date" id="date"></div></div>
  <div class="lbl">Heute</div>
  <div class="items" id="today"></div>
  <div class="foot" id="tomorrow"></div>
</div>
<div class="view ringv" id="klingelt" hidden>
  <div class="top"><div class="clock" data-clock></div><span class="pill">Erinnerung</span></div>
  <div class="big" id="reminder"></div>
  <div class="say">Bitte den Hörer abheben.</div>
</div>
<div class="view" id="gespraech" hidden>
  <div class="top"><div class="date">Gespräch läuft</div><div class="date" data-clock></div></div>
  <div id="conv" style="display:flex;flex-direction:column;gap:2vw;overflow:hidden"></div>
  <div class="foot">Beim Auflegen ist alles weg.</div>
</div>
<div class="view helpv" id="hilfe" hidden>
  <div class="top"><div class="clock" data-clock></div><span class="pill" id="helppill">Hilfe unterwegs</span></div>
  <div class="big" id="helpbig">Ihre Meldung ist unterwegs.</div>
  <div class="say" id="helptext"></div>
  <div class="foot">Bei Lebensgefahr: 144 anrufen.</div>
</div>
<div class="offline" id="offline" hidden>Keine Verbindung zum Gerät</div>
<script>
const $=id=>document.getElementById(id);
const TZ={timeZone:"Europe/Zurich"};
function tick(){const d=new Date();
 const t=d.toLocaleTimeString("de-CH",{...TZ,hour:"2-digit",minute:"2-digit"});
 document.querySelectorAll("[data-clock]").forEach(e=>e.textContent=t);
 $("date").textContent=d.toLocaleDateString("de-CH",{...TZ,weekday:"long",day:"numeric",month:"long"});}
function el(tag,cls,text){const e=document.createElement(tag);if(cls)e.className=cls;if(text!=null)e.textContent=text;return e;}
function render(s){
 ["ruhe","klingelt","gespraech","hilfe"].forEach(m=>$(m).hidden=m!==s.modus);
 const today=$("today");today.replaceChildren();
 if(!s.heute.length)today.append(el("div","empty","Heute stehen keine Termine an."));
 s.heute.forEach(i=>{const r=el("div","item"+(i.vorbei?" done":"")+(i.naechster?" next":""));
  r.append(el("b",null,i.zeit),el("span",null,i.titel));today.append(r);});
 $("tomorrow").textContent=s.morgen?"Morgen: "+s.morgen:"";
 $("reminder").textContent=s.erinnerung||"Erinnerung";
 const conv=$("conv");conv.replaceChildren();
 s.gespraech.slice(-2).forEach(l=>{const d=el("div","say"+(l.who==="senior"?" me":""));
  d.append(el("span","who",l.who==="senior"?"Sie":"SeniorVoice"),document.createTextNode(l.text));conv.append(d);});
 const h=s.hilfe||{};const ht=$("helptext");ht.replaceChildren();
 $("helppill").textContent=h.phase==="abgebrochen"?"Hilfe abgebrochen":(h.phase==="wartet"?"Hilfe"+(h.rest?" · noch "+h.rest+" s":""):"Hilfe unterwegs");
 $("helpbig").textContent=h.phase==="abgebrochen"?"Abgebrochen.":(h.phase==="wartet"?"Gleich wird "+(h.kontakt||"Ihre Kontaktperson")+" informiert.":"Ihre Meldung ist unterwegs.");
 if(h.phase==="abgebrochen")ht.textContent="Es wird niemand informiert. Brauchen Sie doch Hilfe? Nochmals «Hilfe» drücken.";
 else if(h.phase==="wartet")ht.textContent="Aus Versehen gedrückt? Nochmals «Hilfe» drücken.";
 else if(h.kontakt){ht.append(el("span",h.zugestellt?"ok":null,(h.zugestellt?"✓ ":"")+h.kontakt+(h.rolle?" ("+h.rolle+")":"")+(h.zugestellt?" ist benachrichtigt.":" wird benachrichtigt …")));
  ht.append(el("br"),document.createTextNode("Wir warten auf eine Antwort."));}
 else ht.textContent="Die Meldung wird verschickt …";}
async function refresh(){try{const r=await fetch("/screen/state",{cache:"no-store"});if(!r.ok)throw 0;
 render(await r.json());$("offline").hidden=true;}catch(e){$("offline").hidden=false;}}
tick();setInterval(tick,1000);refresh();setInterval(refresh,1000);
</script></body></html>
"""
