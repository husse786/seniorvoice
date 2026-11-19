"""Simulated telephone as a web page (core_service.py --input web).

Stands in for the hook switch and the six buttons as long as the telephone
hardware is not assembled: the same events go into the same core queue as
from GPIO, so everything behind it is the real device software. The page
also shows the ringing, the state of the device and, in the text mode of
the simulation (SIM_AUDIO=text), the conversation as text with a field to
type what the senior says. A second panel stands in for the phone of the
Help contact (alert received, "Ich kümmere mich").

Only reachable from this computer (127.0.0.1). POST requests need the header
X-Sim-Phone, so another web page in the same browser cannot press buttons.
Shown sentences live in RAM only and are cleared when the handset is hung up
(the conversation is forgotten, A8). Python standard library only.
"""

import collections
import ipaddress
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

from hardware import BUTTONS, InputEvent, InputSource
from logging_config import get_logger

log = get_logger("sim_phone")

MAX_LINES = 60
MAX_TEXT = 500
MAX_BODY = 2048
OUTPUT_LABELS = {"handset": "Hörer", "speaker": "Lautsprecher", "kanal": "Kontakt-Handy",
                 "senior": "Seniorin/Senior"}


class SimPhone(InputSource):
    def __init__(self, port: int, state: Callable[[], dict] | None = None,
                 text_mode: bool = False, host: str = "127.0.0.1"):
        self.port = port
        self.host = host
        self.text_mode = text_mode
        self._state = state or (lambda: {})
        self._lines: collections.deque = collections.deque(maxlen=MAX_LINES)
        self._seq = 0
        self._lock = threading.Lock()
        self.events = None
        self.server: ThreadingHTTPServer | None = None

    # --- what the device says / the contact receives (RAM only) ---

    def show(self, text: str, output: str = "handset") -> None:
        who = "kontakt" if output == "kanal" else "geraet"
        self._add(who, output, text)

    def _add(self, who: str, output: str, text: str) -> None:
        with self._lock:
            self._seq += 1
            self._lines.append({"id": self._seq, "t": time.strftime("%H:%M:%S"),
                                "who": who, "output": output,
                                "label": OUTPUT_LABELS.get(output, output),
                                "text": text[:MAX_TEXT * 2]})

    def forget_conversation(self) -> None:
        """Hung up: the conversation disappears from the page (A8)."""
        with self._lock:
            self._lines = collections.deque(
                (line for line in self._lines if line["output"] in ("speaker", "kanal")),
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
        if not self.text_mode:
            return "Textmodus ist aus (SIM_AUDIO=text)"
        if not text or len(text) > MAX_TEXT:
            return f"1 bis {MAX_TEXT} Zeichen"
        if not self._state().get("in_call"):
            return "Bitte zuerst den Hörer abheben"
        self._add("senior", "senior", text)
        self.events.put(InputEvent("sim_text", text))
        return None

    def snapshot(self) -> dict:
        state = dict(self._state())
        state.update(text_mode=self.text_mode, lines=self.lines())
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
:root{--bg:#f4f1ea;--card:#fff;--ink:#1d2a33;--muted:#5d6b75;--line:#d9d3c7;--accent:#16324a;
--green:#1f7a4d;--red:#b3261e;--amber:#b26a00}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
header{background:var(--accent);color:#fff;padding:.8rem 1.2rem;display:flex;gap:1rem;align-items:center;flex-wrap:wrap}
header h1{font-size:1.1rem;margin:0}.badge{background:#ffffff22;border-radius:99px;padding:.15rem .7rem;font-size:.85rem}
main{display:grid;grid-template-columns:minmax(300px,420px) 1fr;gap:1.2rem;padding:1.2rem;max-width:1200px;margin:auto}
@media(max-width:800px){main{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:1rem 1.1rem}
h2{font-size:1rem;margin:.1rem 0 .8rem}
.phone{text-align:center}
.status{font-size:1.15rem;font-weight:650;margin:.3rem 0 1rem;min-height:1.6em}
.ring{animation:ring .35s infinite alternate}@keyframes ring{from{transform:rotate(-4deg)}to{transform:rotate(4deg)}}
.handset{width:100%;padding:1rem;border-radius:14px;border:0;font-size:1.15rem;font-weight:700;cursor:pointer;color:#fff;background:var(--green)}
.handset.off{background:#3d4b55}
.buttons{display:grid;grid-template-columns:repeat(3,1fr);gap:.6rem;margin-top:1rem}
.buttons button{padding:1rem .3rem;border-radius:12px;border:2px solid var(--accent);background:#fff;color:var(--accent);font-weight:700;font-size:1rem;cursor:pointer}
.buttons button.hilfe{background:var(--red);border-color:var(--red);color:#fff}
.meta{display:flex;flex-wrap:wrap;gap:.4rem;justify-content:center;margin-top:1rem;font-size:.85rem;color:var(--muted)}
.meta span{border:1px solid var(--line);border-radius:99px;padding:.1rem .6rem}
.log{display:flex;flex-direction:column;gap:.5rem;max-height:52vh;overflow:auto;padding-right:.3rem}
.line{border-radius:12px;padding:.5rem .7rem;max-width:85%}
.line small{display:block;color:var(--muted);font-size:.75rem}
.geraet{background:#e8eef4;align-self:flex-start}.senior{background:#e3f1e8;align-self:flex-end}
.kontakt{background:#fbefd9;align-self:flex-start;border:1px dashed var(--amber)}
.empty{color:var(--muted)}
form{display:flex;gap:.5rem;margin-top:.8rem}input{flex:1;padding:.7rem;border-radius:10px;border:1px solid var(--line);font-size:1rem}
form button,.ack{padding:.7rem 1rem;border-radius:10px;border:0;background:var(--accent);color:#fff;font-weight:700;cursor:pointer}
.ack{background:var(--amber);margin-top:.6rem;width:100%}
.hint{color:var(--muted);font-size:.85rem;margin:.6rem 0 0}
.err{color:var(--red);min-height:1.2em;font-size:.9rem}
</style></head><body>
<header><h1>SeniorVoice · simuliertes Telefon</h1><span class="badge" id="mode"></span>
<span class="badge">Echte Gerätesoftware · nur Gabel, Knöpfe und Ton simuliert</span></header>
<main>
<section class="card phone" aria-label="Telefon">
  <div class="status" id="status" role="status" aria-live="polite">…</div>
  <button class="handset" id="hook" type="button">Hörer abheben</button>
  <div class="buttons">
    <button type="button" data-b="sprechen">Sprechen</button><button type="button" data-b="heute">Heute</button>
    <button type="button" data-b="kalender">Kalender</button><button type="button" data-b="rat">Rat</button>
    <button type="button" data-b="familie">Familie</button><button type="button" data-b="hilfe" class="hilfe">Hilfe</button>
  </div>
  <div class="meta" id="meta"></div>
  <p class="err" id="err"></p>
</section>
<section class="card" aria-label="Gespräch">
  <h2 id="loghead">Was das Gerät sagt</h2>
  <div class="log" id="log"><p class="empty">Noch nichts.</p></div>
  <form id="say" hidden><input id="text" maxlength="500" autocomplete="off" placeholder="Was die Seniorin/der Senior sagt …" aria-label="Was die Seniorin oder der Senior sagt"><button>Sagen</button></form>
  <button class="ack" id="ack" type="button" hidden>Kontaktperson: «Ich kümmere mich»</button>
  <p class="hint">Das Gespräch steht nur im Arbeitsspeicher und verschwindet beim Auflegen. Nichts davon wird gespeichert.</p>
</section>
</main>
<script>
const $=id=>document.getElementById(id);let inCall=false,lastId=0;
const DIALOG={bereit:"KI bereit",laedt:"KI lädt …",neustart:"KI startet neu",unbekannt:"KI: ?"};
async function post(path,body){$("err").textContent="";try{const r=await fetch(path,{method:"POST",headers:{"Content-Type":"application/json","X-Sim-Phone":"1"},body:JSON.stringify(body)});
if(!r.ok){const j=await r.json().catch(()=>({}));$("err").textContent=j.error||"Fehler";}}catch(e){$("err").textContent="Gerät nicht erreichbar";}refresh();}
$("hook").onclick=()=>post("/event",{kind:inCall?"hook_on":"hook_off"});
document.querySelectorAll("[data-b]").forEach(b=>b.onclick=()=>post("/event",{kind:"button",name:b.dataset.b}));
$("ack").onclick=()=>post("/event",{kind:"sim_ack"});
$("say").onsubmit=e=>{e.preventDefault();const t=$("text").value.trim();if(t){post("/say",{text:t});$("text").value="";}};
function render(s){inCall=!!s.in_call;const st=$("status");
 st.textContent=s.ringing?"Es klingelt – bitte abheben":(s.announcing?"Ansage läuft …":(inCall?"Gespräch läuft":"Aufgelegt"));
 st.classList.toggle("ring",!!s.ringing);
 $("hook").textContent=inCall?"Auflegen":"Hörer abheben";$("hook").classList.toggle("off",inCall);
 $("mode").textContent=s.text_mode?"Textmodus":"Ton über Mikrofon und Lautsprecher";
 $("say").hidden=!(s.text_mode&&inCall);$("loghead").textContent=s.text_mode?"Gespräch (als Text)":"Ansagen und Kontakt-Handy";
 $("ack").hidden=!s.help_open;
 $("meta").innerHTML="";[DIALOG[s.dialog]||s.dialog,s.help_open?"Hilfe läuft":"",s.input==="web"?"Eingabe: Web":""].filter(Boolean)
  .forEach(t=>{const x=document.createElement("span");x.textContent=t;$("meta").appendChild(x);});
 const log=$("log");const lines=s.lines||[];const newest=lines.length?lines[lines.length-1].id:0;
 if(newest!==lastId||!lines.length){lastId=newest;log.innerHTML="";
  if(!lines.length){const p=document.createElement("p");p.className="empty";p.textContent="Noch nichts.";log.appendChild(p);}
  lines.forEach(l=>{const d=document.createElement("div");d.className="line "+l.who;const m=document.createElement("small");
   m.textContent=l.t+" · "+l.label;d.appendChild(m);d.appendChild(document.createTextNode(l.text));log.appendChild(d);});
  log.scrollTop=log.scrollHeight;}}
async function refresh(){try{const r=await fetch("/state");render(await r.json());}catch(e){$("status").textContent="Gerät nicht erreichbar";}}
setInterval(refresh,500);refresh();
</script></body></html>
"""
