"""Simulated telephone as a web page (core_service.py --input web).

Stands in for the hook switch and the six buttons as long as the telephone
hardware is not assembled: the same events go into the same core queue as
from GPIO, so everything behind it is the real device software. The page
is drawn as a desk telephone: the handset is lifted by a click, the six keys
are pressed, and the device screen (screen.py, the same page as on the Pi's
display) sits in the phone. Beside it the conversation is shown as text, with
a field to type what the senior says (in text mode instead of speaking, in
audio mode as an alternative). Messages to the Help contact appear there too,
with a button for the contact's "Ich kümmere mich".

Only reachable from this computer (127.0.0.1). POST requests need the header
X-Sim-Phone, so another web page in the same browser cannot press buttons.
Shown sentences live in RAM only and are cleared when the handset is hung up
(the conversation is forgotten, A8). Python standard library only.
"""

import collections
import ipaddress
import json
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

from zoneinfo import ZoneInfo

import screen as screen_page
from hardware import BUTTONS, InputEvent, InputSource
from logging_config import get_logger

log = get_logger("sim_phone")

MAX_LINES = 60
MAX_TEXT = 500
MAX_BODY = 2048
OUTPUT_LABELS = {"hinweis": "Hinweis", "handset": "Hörer", "speaker": "Lautsprecher", "kanal": "Kontakt-Handy",
                 "senior": "getippt", "gesprochen": "gesprochen"}
LOCAL_TZ = ZoneInfo("Europe/Zurich")


class SimPhone(InputSource):
    def __init__(self, port: int, state: Callable[[], dict] | None = None,
                 text_mode: bool = False, host: str = "127.0.0.1", audio_note: str = ""):
        self.port = port
        self.host = host
        self.text_mode = text_mode
        self.audio_note = audio_note      # why there is no sound, or ""
        self._state = state or (lambda: {})
        self._lines: collections.deque = collections.deque(maxlen=MAX_LINES)
        self._seq = 0
        self._lock = threading.Lock()
        self.events = None
        self.server: ThreadingHTTPServer | None = None
        self.screen = None                # screen.Screen, set by the core

    # --- what the device says / the contact receives (RAM only) ---

    def show(self, text: str, output: str = "handset") -> None:
        who = {"kanal": "kontakt", "hinweis": "hinweis"}.get(output, "geraet")
        self._add(who, output, text)

    def heard(self, text: str) -> None:
        """What the senior said into the microphone (speech recognition)."""
        self._add("senior", "gesprochen", text)

    def _add(self, who: str, output: str, text: str) -> None:
        with self._lock:
            self._seq += 1
            self._lines.append({"id": self._seq, "t": datetime.now(LOCAL_TZ).strftime("%H:%M:%S"),
                                "who": who, "output": output,
                                "label": OUTPUT_LABELS.get(output, output),
                                "text": text[:MAX_TEXT * 2]})

    def forget_conversation(self) -> None:
        """Hung up: the conversation disappears from the page (A8)."""
        with self._lock:
            self._lines = collections.deque(
                (line for line in self._lines if line["output"] in ("speaker", "kanal", "hinweis")),
                maxlen=MAX_LINES)

    def lines(self) -> list[dict]:
        with self._lock:
            return list(self._lines)

    # --- input ---

    def press(self, kind: str, name: str = "") -> str | None:
        """Returns an error text, or None if the event was queued."""
        if self.events is None:
            return "Telefon noch nicht bereit"
        if kind in ("hook_off", "hook_on", "sim_ack"):
            self.events.put(InputEvent(kind))
            if kind == "hook_on":
                self.forget_conversation()
            return None
        if kind == "button" and name in BUTTONS:
            self.events.put(InputEvent("button", name))
            return None
        return "unbekannte Taste"

    def say(self, text: str) -> str | None:
        text = " ".join(text.split())
        if not text or len(text) > MAX_TEXT:
            return f"1 bis {MAX_TEXT} Zeichen"
        if not self._state().get("in_call"):
            return "Bitte zuerst den Hörer abheben"
        self._add("senior", "senior", text)
        self.events.put(InputEvent("sim_text", text))
        return None

    def snapshot(self) -> dict:
        state = dict(self._state())
        state.update(text_mode=self.text_mode, audio_note=self.audio_note, lines=self.lines())
        return state

    def start(self, events) -> None:
        address = ipaddress.ip_address(self.host)      # ValueError for names
        if address.is_unspecified:
            raise ValueError("SIM_PHONE_HOST: 127.0.0.1 or the WireGuard address, "
                             "not all interfaces")
        self.events = events
        phone = self

        class Handler(_Handler):
            sim = phone
        self.server = ThreadingHTTPServer((self.host, self.port), Handler)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, name="sim-phone",
                         daemon=True).start()
        log.info("Simulated telephone: http://%s:%d", self.host, self.port)

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()


class _Handler(BaseHTTPRequestHandler):
    sim: SimPhone
    server_version = "SeniorVoiceSim"
    sys_version = ""

    def log_message(self, fmt, *args):
        pass                      # requests may carry typed text: no HTTP log

    def _host_ok(self) -> bool:
        # Against DNS rebinding: only requests addressed to this computer
        host = self.headers.get("Host", "").rsplit(":", 1)[0].strip("[]")
        return host in ("127.0.0.1", "localhost", "::1", self.sim.host)

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; style-src 'unsafe-inline'; "
                         "script-src 'unsafe-inline'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def do_GET(self):
        if not self._host_ok():
            return self._json(403, {"error": "forbidden"})
        if self.path == "/":
            return self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        if self.path == "/state":
            return self._json(200, self.sim.snapshot())
        if screen_page.send_page(self, self.sim.screen, self.path):
            return
        self._json(404, {"error": "not found"})

    def do_POST(self):
        if not self._host_ok() or self.headers.get("X-Sim-Phone") != "1":
            return self._json(403, {"error": "forbidden"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 <= length <= MAX_BODY:
                raise ValueError
            data = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(data, dict):
                raise ValueError
        except (ValueError, UnicodeDecodeError):
            return self._json(400, {"error": "JSON erwartet"})
        if self.path == "/event":
            error = self.sim.press(str(data.get("kind", "")), str(data.get("name", "")))
        elif self.path == "/say":
            error = self.sim.say(str(data.get("text", "")))
        else:
            return self._json(404, {"error": "not found"})
        if error:
            return self._json(400, {"error": error})
        self._json(200, {"ok": True})


PAGE = """<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SeniorVoice – simuliertes Telefon</title>
<style>
/* A drawn desk telephone (CSS only, no 3D library), conversation beside it */
:root{--bg:#e9e6df;--card:#fff;--ink:#1d2a33;--muted:#5d6b75;--line:#d4cec2;--accent:#16324a;
--green:#1f7a4d;--red:#b3261e;--amber:#b26a00;
--body1:#f7f5f0;--body2:#d9d4c9;--body3:#bdb6a8;--key1:#fff;--key2:#e4e0d7;--keyink:#16324a;--hs1:#2b3a45;--hs2:#141d24}
@media (prefers-color-scheme: dark){:root{--bg:#11171b;--card:#1c252c;--ink:#e8e4dc;--muted:#9aa7b0;--line:#2f3a42;--accent:#8fb6d8;color-scheme:dark}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
header{background:#16324a;color:#fff;padding:.7rem 1.2rem;display:flex;gap:1rem;align-items:center;flex-wrap:wrap}
header h1{font-size:1.05rem;margin:0}.badge{background:#ffffff22;border-radius:99px;padding:.15rem .7rem;font-size:.82rem}
main{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(0,1fr);gap:18px;align-items:start;padding:16px;max-width:1300px;margin:auto}
@media(max-width:900px){main{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:1rem 1.1rem;min-width:0}
h2{font-size:.95rem;margin:.1rem 0 .7rem}
.stage{perspective:1400px;padding:60px 0 10px;overflow:hidden;display:flex;justify-content:center}
.phone{position:relative;width:min(640px,100%);aspect-ratio:640/470;transform:rotateX(14deg);container-type:inline-size}
.base{position:absolute;inset:0;border-radius:6cqw 6cqw 4cqw 4cqw;background:linear-gradient(180deg,var(--body1) 0%,var(--body2) 70%,var(--body3) 100%);
box-shadow:0 3cqw 0 -.4cqw #a59d8d,0 5cqw 6cqw rgba(0,0,0,.35),inset 0 .5cqw 0 rgba(255,255,255,.8)}
.cradle{position:absolute;left:4cqw;top:4cqw;width:22cqw;bottom:4cqw;border-radius:4cqw;background:linear-gradient(90deg,#cfc9bc,#e7e3da 40%,#cfc9bc);box-shadow:inset 0 .6cqw 1.4cqw rgba(0,0,0,.25)}
.handset{position:absolute;left:5.5cqw;top:3cqw;width:19cqw;height:calc(100% - 6cqw);cursor:pointer;border:0;padding:0;background:none;
transition:transform .55s cubic-bezier(.3,1.4,.5,1);transform-origin:50% 100%;z-index:3}
.handset .shape{position:absolute;inset:0;border-radius:9cqw;background:linear-gradient(90deg,var(--hs2),var(--hs1) 45%,var(--hs2));box-shadow:0 1.5cqw 2.5cqw rgba(0,0,0,.45),inset 0 .4cqw 0 rgba(255,255,255,.15)}
.handset .cup{position:absolute;left:50%;width:15cqw;height:15cqw;transform:translateX(-50%);border-radius:50%;background:radial-gradient(circle at 50% 40%,#3a4a55,#151d23 70%);box-shadow:inset 0 0 0 .5cqw #0d1418}
.handset .cup.top{top:2cqw}.handset .cup.bot{bottom:2cqw}
.handset .label{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%) rotate(-90deg);white-space:nowrap;background:var(--green);color:#fff;font-weight:800;font-size:3.4cqw;padding:1cqw 3cqw;border-radius:99px;box-shadow:0 .5cqw 1cqw rgba(0,0,0,.4)}
.phone.lifted .handset{transform:translate(3cqw,-9cqw) rotate(-10deg)}
.phone.lifted .handset .label{background:#3d4b55}
.phone.ringing .handset{animation:ring .12s infinite alternate}
@keyframes ring{from{transform:rotate(-2.5deg)}to{transform:rotate(2.5deg)}}
@media (prefers-reduced-motion: reduce){.phone.ringing .handset{animation:none}.handset{transition:none}}
.bezel{position:absolute;left:30cqw;right:5cqw;top:4.5cqw;aspect-ratio:800/480;border-radius:2.4cqw;padding:1.6cqw;background:linear-gradient(180deg,#2a2f33,#0b0e10);box-shadow:inset 0 .4cqw .8cqw rgba(0,0,0,.6),0 .3cqw 0 rgba(255,255,255,.7)}
.bezel iframe{width:100%;height:100%;border:0;border-radius:.8cqw;display:block;background:#0f1b24}
.keys{position:absolute;left:30cqw;right:5cqw;bottom:5cqw;display:grid;grid-template-columns:repeat(3,1fr);gap:2cqw}
.key{border:0;cursor:pointer;border-radius:2.2cqw;padding:2.3cqw 0;font:800 3.3cqw/1 system-ui,sans-serif;color:var(--keyink);background:linear-gradient(180deg,var(--key1),var(--key2));box-shadow:0 1.1cqw 0 #a89f8f,0 1.6cqw 1.6cqw rgba(0,0,0,.25);transition:transform .08s,box-shadow .08s}
.key:active{transform:translateY(.9cqw);box-shadow:0 .2cqw 0 #a89f8f,0 .4cqw .6cqw rgba(0,0,0,.25)}
.key.hilfe{background:linear-gradient(180deg,#d8463d,#a81f18);color:#fff;box-shadow:0 1.1cqw 0 #6e130e,0 1.6cqw 1.6cqw rgba(0,0,0,.3)}
.key:focus-visible,.handset:focus-visible{outline:3px solid var(--amber);outline-offset:3px}
.led{position:absolute;right:6cqw;top:1.6cqw;width:1.6cqw;height:1.6cqw;border-radius:50%;background:#9aa;}
.led.on{background:#7ccf9a;box-shadow:0 0 1.4cqw #7ccf9a}.led.warn{background:#e0a030;box-shadow:0 0 1.4cqw #e0a030}
.speaker{position:absolute;left:30cqw;top:1.4cqw;display:flex;gap:.8cqw}.speaker i{width:4cqw;height:.7cqw;border-radius:9px;background:#b9b2a3}
.caption{text-align:center;color:var(--muted);font-size:.9rem;margin:.6rem 0 0;font-weight:600}
.meta{display:flex;flex-wrap:wrap;gap:.4rem;justify-content:center;margin-top:.4rem;font-size:.82rem;color:var(--muted)}
.meta span{border:1px solid var(--line);border-radius:99px;padding:.1rem .6rem}
.log{display:flex;flex-direction:column;gap:.45rem;max-height:52vh;overflow:auto;min-height:6rem}
.line{border-radius:12px;padding:.45rem .7rem;max-width:88%;font-size:.95rem}
.line small{display:block;color:var(--muted);font-size:.72rem}
.hinweis{background:color-mix(in srgb,var(--red) 12%,var(--card));align-self:stretch;max-width:none}
.geraet{background:color-mix(in srgb,var(--accent) 14%,var(--card));align-self:flex-start}
.senior{background:color-mix(in srgb,var(--green) 16%,var(--card));align-self:flex-end}
.kontakt{background:color-mix(in srgb,var(--amber) 16%,var(--card));align-self:flex-start;border:1px dashed var(--amber)}
.empty{color:var(--muted)}
form{display:flex;gap:.5rem;margin-top:.7rem}
input{flex:1;min-width:0;padding:.65rem;border-radius:10px;border:1px solid var(--line);font-size:1rem;background:var(--card);color:var(--ink)}
form button,.ack{padding:.65rem 1rem;border-radius:10px;border:0;background:var(--accent);color:var(--card);font-weight:700;cursor:pointer}
.ack{background:var(--amber);color:#fff;margin-top:.6rem;width:100%}
.hint{color:var(--muted);font-size:.82rem;margin:.5rem 0 0}
.err{color:var(--red);min-height:1.2em;font-size:.9rem;text-align:center;margin:.3rem 0 0}
</style></head><body>
<header><h1>SeniorVoice · simuliertes Telefon</h1><span class="badge" id="mode"></span>
<span class="badge">Echte Gerätesoftware · nur Gabel, Tasten und Ton simuliert</span></header>
<main>
<section class="card" aria-label="Telefon">
  <div class="stage"><div class="phone" id="phone">
    <div class="base"></div><div class="cradle"></div>
    <button class="handset" id="hook" type="button" aria-label="Hörer abheben">
      <span class="shape"></span><span class="cup top"></span><span class="cup bot"></span>
      <span class="label" id="hookLabel">Abheben</span></button>
    <div class="speaker" aria-hidden="true"><i></i><i></i><i></i><i></i></div>
    <span class="led" id="led" aria-hidden="true"></span>
    <div class="bezel"><iframe src="/screen" title="Bildschirm am Gerät"></iframe></div>
    <div class="keys">
      <button class="key" type="button" data-b="sprechen">Sprechen</button>
      <button class="key" type="button" data-b="heute">Heute</button>
      <button class="key" type="button" data-b="kalender">Kalender</button>
      <button class="key" type="button" data-b="rat">Rat</button>
      <button class="key" type="button" data-b="familie">Familie</button>
      <button class="key hilfe" type="button" data-b="hilfe">Hilfe</button>
    </div>
  </div></div>
  <p class="caption" id="status" role="status" aria-live="polite">…</p>
  <div class="meta" id="meta"></div>
  <p class="err" id="err"></p>
  <p class="hint" id="note" hidden></p>
</section>
<section class="card" aria-label="Gespräch">
  <h2>Gespräch als Text</h2>
  <div class="log" id="log"><p class="empty">Noch nichts.</p></div>
  <form id="say"><input id="text" maxlength="500" autocomplete="off" placeholder="Tippen statt sprechen …" aria-label="Tippen statt sprechen"><button>Sagen</button></form>
  <button class="ack" id="ack" type="button" hidden>Kontaktperson: «Ich kümmere mich»</button>
  <p class="hint">Steht nur im Arbeitsspeicher. Beim Auflegen verschwindet das Gespräch. Durchsagen über den Lautsprecher und Meldungen an die Kontaktperson bleiben stehen, bis das Gerät neu startet.</p>
</section>
</main>
<script>
const $=id=>document.getElementById(id);let inCall=false,lastId=-1;
const DIALOG={bereit:"KI bereit",laedt:"KI lädt …",neustart:"KI startet neu",unbekannt:"KI: ?"};
async function post(path,body){$("err").textContent="";try{const r=await fetch(path,{method:"POST",headers:{"Content-Type":"application/json","X-Sim-Phone":"1"},body:JSON.stringify(body)});
if(!r.ok){const j=await r.json().catch(()=>({}));$("err").textContent=j.error||"Fehler";}}catch(e){$("err").textContent="Gerät nicht erreichbar";}refresh();}
$("hook").onclick=()=>post("/event",{kind:inCall?"hook_on":"hook_off"});
document.querySelectorAll("[data-b]").forEach(b=>b.onclick=()=>post("/event",{kind:"button",name:b.dataset.b}));
$("ack").onclick=()=>post("/event",{kind:"sim_ack"});
$("say").onsubmit=e=>{e.preventDefault();const t=$("text").value.trim();if(t){post("/say",{text:t});$("text").value="";}};
function render(s){inCall=!!s.in_call;
 const HP={wartet:"Hilfe: wird gleich verschickt – nochmals «Hilfe» bricht ab",unterwegs:"Hilfe läuft",abgebrochen:"Hilfe abgebrochen, niemand informiert"};
 const hp=s.help_phase||(s.help_open?"unterwegs":"");
 const busy=s.ringing||s.in_call||s.announcing;
 const hs=hp&&!(hp==="abgebrochen"&&busy)?HP[hp]||"Hilfe läuft":"";
 $("status").textContent=hs?hs:(s.ringing?"Es klingelt – bitte abheben":(s.announcing?"Ansage läuft …":(inCall?"Gespräch läuft":"Aufgelegt")));
 const p=$("phone");p.classList.toggle("lifted",inCall);p.classList.toggle("ringing",!!s.ringing&&!inCall);
 $("hookLabel").textContent=inCall?"Auflegen":"Abheben";$("hook").setAttribute("aria-label",inCall?"Hörer auflegen":"Hörer abheben");
 $("led").className="led "+(s.dialog==="bereit"?"on":"warn");
 $("mode").textContent=s.text_mode?"Nur Tippen":"Sprechen oder tippen";
 $("note").textContent=s.audio_note||"";$("note").hidden=!s.audio_note;
 $("ack").hidden=hp!=="unterwegs";
 $("meta").replaceChildren();[DIALOG[s.dialog]||s.dialog,hs].filter(Boolean)
  .forEach(t=>{const x=document.createElement("span");x.textContent=t;$("meta").appendChild(x);});
 const log=$("log");const lines=s.lines||[];const newest=lines.length?lines[lines.length-1].id:0;
 if(newest!==lastId||lines.length!==log.querySelectorAll(".line").length){lastId=newest;log.replaceChildren();
  if(!lines.length){const e=document.createElement("p");e.className="empty";e.textContent="Noch nichts.";log.appendChild(e);}
  lines.forEach(l=>{const d=document.createElement("div");d.className="line "+l.who;const m=document.createElement("small");
   m.textContent=l.t+" · "+l.label;d.appendChild(m);d.appendChild(document.createTextNode(l.text));log.appendChild(d);});
  log.scrollTop=log.scrollHeight;}}
async function refresh(){try{const r=await fetch("/state");render(await r.json());}catch(e){$("status").textContent="Gerät nicht erreichbar";}}
setInterval(refresh,500);refresh();
</script></body></html>
"""
