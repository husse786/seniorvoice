"""Simulated telephone (web page, text mode), metrics.db and the health view."""

import io
import json
import queue
import sqlite3
import sys
import threading
import time
import types
import urllib.error
import urllib.request
from datetime import datetime, timedelta

import pytest

from conftest import patch_http

SECRET_SENTENCE = "Ich bin heute gestuerzt Geheimsatz5150"
ANSWER = "Das tut mir leid Antwortsatz7070"
TOKEN = "health-token-1"


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


# --- metrics.db -------------------------------------------------------------

def test_metrics_go_to_their_own_file(env):
    log = env.load("interaction_log")
    log.log_interaction("handset", stt_duration_ms=100, llm_duration_ms=900,
                        tts_duration_ms=300, total_duration_ms=1500)
    assert env.metrics_path.exists()
    conn = sqlite3.connect(env.metrics_path)
    assert conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0] == 1
    conn.close()
    # The senior's database is not touched by metrics
    if env.db_path.exists():
        conn = sqlite3.connect(env.db_path)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master")}
        conn.close()
        assert "interactions" not in tables


def test_benchmarks_default_to_metrics_db(env):
    config = env.load("config")
    assert config.DB_PATH == str(env.metrics_path)


def test_daily_summary_only_aggregates(env):
    metrics = env.load("metrics")
    for llm in (1000, 2000, 3000, 4000):
        metrics.log_interaction("handset", stt_duration_ms=500, llm_duration_ms=llm,
                                tts_duration_ms=200, total_duration_ms=llm + 700)
    metrics.log_interaction("handset", error="no_speech")
    metrics.log_event("dialog_restart")
    days = metrics.daily_summary(7)
    assert len(days) == 7
    today = days[0]
    assert today["date"] == datetime.now().strftime("%Y-%m-%d")
    assert today["turns"] == 5
    assert today["errors"] == {"no_speech": 1}
    assert today["events"] == {"dialog_restart": 1}
    assert today["llm_ms"] == {"p50": 2000, "p95": 4000}
    assert today["answer_ms"] == {"p50": 2500, "p95": 4500}
    # Only daily values leave the summary, no single timestamps
    assert all(set(d) == {"date", "turns", "errors", "events", "stt_ms", "llm_ms",
                          "tts_ms", "answer_ms"} for d in days)


def test_service_events_are_a_fixed_list(env):
    metrics = env.load("metrics")
    with pytest.raises(ValueError):
        metrics.log_event("Frau Keller hat angerufen")


def test_metrics_purge_keeps_recent_rows(env):
    metrics = env.load("metrics")
    metrics.log_interaction("handset", llm_duration_ms=10)
    conn = metrics.connect()
    old = (datetime.now() - timedelta(days=40)).strftime("%Y-%m-%dT%H:%M:%S")
    conn.execute("INSERT INTO interactions (timestamp, trigger_type) VALUES (?, 'handset')", (old,))
    conn.commit()
    conn.close()
    assert metrics.purge() == 1
    conn = metrics.connect()
    assert conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0] == 1
    conn.close()


# --- text mode --------------------------------------------------------------

def _fake_llm(monkeypatch):
    import llm_backend

    def urlopen(req, timeout=None):
        body = {"choices": [{"message": {"content": ANSWER}}]}
        return _FakeResponse(json.dumps(body).encode("utf-8"))
    patch_http(llm_backend, monkeypatch, urlopen)


def test_text_mode_turn_needs_no_audio_and_stores_no_text(env, monkeypatch):
    env.set(SIM_AUDIO="text", LOG_LEVEL="DEBUG")
    main = env.load("main")
    # Microphone, Whisper and Piper must not be touched in text mode
    for name in ("audio_capture", "stt", "faster_whisper"):
        broken = types.ModuleType(name)
        monkeypatch.setitem(sys.modules, name, broken)
    _fake_llm(monkeypatch)
    import sim_text
    shown = []
    sim_text.set_sink(lambda text, output: shown.append((text, output)))
    sim_text.put_input(SECRET_SENTENCE)
    try:
        history, _ = main.run_pipeline(use_pir=False, history=[], trigger="handset")
    finally:
        sim_text.set_sink(None)
    assert history[-1]["content"] == ANSWER
    assert (ANSWER, "handset") in shown
    for handler in __import__("logging").getLogger().handlers:
        handler.flush()
    assert env.files_containing("Geheimsatz5150") == []
    assert env.files_containing("Antwortsatz7070") == []
    conn = sqlite3.connect(env.metrics_path)
    assert conn.execute("SELECT stt_duration_ms FROM interactions").fetchall() == [(0,)]
    conn.close()


def test_text_mode_returns_when_hung_up(env):
    env.set(SIM_AUDIO="text")
    sim_text = env.load("sim_text")
    active = {"on": True}
    threading.Timer(0.3, lambda: active.update(on=False)).start()
    start = time.monotonic()
    assert sim_text.wait_input(lambda: active["on"], timeout=10) == ""
    assert time.monotonic() - start < 2


def test_dialog_takes_typed_text_from_the_bus(env):
    env.set(SIM_AUDIO="text")
    dialog = env.load("dialog_service")
    import sim_text
    service = dialog.DialogService(types.SimpleNamespace(send=lambda *a, **k: True))
    service.on_message({"type": "sim_text", "text": "Hallo"})
    service.on_message({"type": "sim_text", "text": 42})        # ignored
    assert sim_text.wait_input(lambda: True, timeout=1) == "Hallo"
    assert sim_text.wait_input(lambda: True, timeout=0.3) == ""


def test_speak_in_text_mode_writes_no_audio(env, monkeypatch):
    env.set(SIM_AUDIO="text")
    tts = env.load("tts")
    import sim_text
    shown = []
    sim_text.set_sink(lambda text, output: shown.append((text, output)))
    monkeypatch.setattr(tts, "synthesize", lambda text: pytest.fail("no audio in text mode"))
    try:
        tts.speak("Guten Tag", output="speaker")
    finally:
        sim_text.set_sink(None)
    assert shown == [("Guten Tag", "speaker")]


def test_mac_player_fallback(env, monkeypatch):
    tts = env.load("tts")
    monkeypatch.setattr(tts.shutil, "which",
                        lambda name: "/usr/bin/afplay" if name == "afplay" else None)
    assert tts.player_command("x.wav") == ["/usr/bin/afplay", "x.wav"]


# --- simulated phone page ---------------------------------------------------

@pytest.fixture
def phone(env):
    env.set(SIM_AUDIO="text")
    sim_phone = env.load("sim_phone")
    state = {"in_call": False}
    p = sim_phone.SimPhone(0, state=lambda: dict(state), text_mode=True)
    events = queue.Queue()
    p.start(events)
    base = f"http://127.0.0.1:{p.server.server_address[1]}"

    def call(method, path, body=None, headers=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(base + path, data=data, method=method)
        for k, v in {"X-Sim-Phone": "1", **(headers or {})}.items():
            if v is not None:
                req.add_header(k, v)
        try:
            with _opener().open(req, timeout=5) as resp:
                raw = resp.read()
                return resp.status, (json.loads(raw) if path != "/" else raw.decode())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())
    call.events, call.state, call.phone = events, state, p
    yield call
    p.stop()


def test_phone_page_and_buttons(phone):
    status, page = phone("GET", "/")
    assert status == 200 and "Hörer abheben" in page and "Hilfe" in page
    assert phone("POST", "/event", {"kind": "hook_off"})[0] == 200
    assert phone("POST", "/event", {"kind": "button", "name": "hilfe"})[0] == 200
    assert phone("POST", "/event", {"kind": "button", "name": "explode"})[0] == 400
    got = [phone.events.get_nowait() for _ in range(2)]
    assert [(e.kind, e.name) for e in got] == [("hook_off", ""), ("button", "hilfe")]


def test_phone_refuses_other_web_pages(phone):
    # Without the custom header (a plain form post from another site)
    assert phone("POST", "/event", {"kind": "hook_off"}, {"X-Sim-Phone": None})[0] == 403
    # DNS rebinding: a request addressed to another host name
    assert phone("GET", "/state", headers={"Host": "evil.example"})[0] == 403
    assert phone.events.empty()


def test_phone_page_never_on_all_interfaces(env):
    sim_phone = env.load("sim_phone")
    for host in ("0.0.0.0", "::", "my-pi.local"):
        with pytest.raises(ValueError):
            sim_phone.SimPhone(0, host=host).start(queue.Queue())


def test_phone_page_on_tunnel_address_accepts_that_host(env):
    # On the Pi the page listens on its WireGuard address; 127.0.0.2 stands in
    sim_phone = env.load("sim_phone")
    p = sim_phone.SimPhone(0, host="127.0.0.2")
    try:
        p.start(queue.Queue())
    except OSError:
        pytest.skip("127.0.0.2 not available here (macOS has only 127.0.0.1)")
    try:
        port = p.server.server_address[1]
        req = urllib.request.Request(f"http://127.0.0.2:{port}/state")
        req.add_header("X-Sim-Phone", "1")
        with _opener().open(req, timeout=5) as resp:
            assert resp.status == 200
        req = urllib.request.Request(f"http://127.0.0.2:{port}/state")
        req.add_header("Host", "evil.example")
        with pytest.raises(urllib.error.HTTPError):
            _opener().open(req, timeout=5)
    finally:
        p.stop()


def test_input_from_environment(env):
    assert env.load("config").SENIORVOICE_INPUT == "keyboard"
    env.set(SENIORVOICE_INPUT="web")
    assert env.load("config").SENIORVOICE_INPUT == "web"


def test_typed_text_only_during_a_call_and_forgotten_on_hang_up(phone):
    assert phone("POST", "/say", {"text": "Hallo"})[0] == 400          # not lifted
    phone.state["in_call"] = True
    assert phone("POST", "/say", {"text": "Hallo Geraet"})[0] == 200
    event = phone.events.get_nowait()
    assert (event.kind, event.name) == ("sim_text", "Hallo Geraet")
    phone.phone.show("Guten Tag", "handset")
    phone.phone.show("Bitte rufen Sie 144 an", "speaker")
    texts = [line["text"] for line in phone("GET", "/state")[1]["lines"]]
    assert texts == ["Hallo Geraet", "Guten Tag", "Bitte rufen Sie 144 an"]
    phone("POST", "/event", {"kind": "hook_on"})
    texts = [line["text"] for line in phone("GET", "/state")[1]["lines"]]
    assert texts == ["Bitte rufen Sie 144 an"]     # conversation gone, room speaker stays


# --- core: forwarding and status file ----------------------------------------

class _Sup:
    def __init__(self):
        self.sent = []
        self.restarts = 2
        self.last_restart = "llm_hang"
        self.on_restart = self.on_ready = None

    def send(self, kind, **fields):
        self.sent.append((kind, fields))
        return True

    def check(self):
        pass

    def health_state(self):
        return "bereit"


def test_core_forwards_typed_text_only_in_a_call(env):
    core_service = env.load("core_service")
    from hardware import InputEvent, SimulatedRinger
    sup = _Sup()
    core = core_service.Core(sup, SimulatedRinger(), with_reminders=False)
    core.handle(InputEvent("sim_text", "Hallo"))
    assert sup.sent == []
    core.handle(InputEvent("hook_off"))
    core.handle(InputEvent("sim_text", "Hallo"))
    assert ("sim_text", {"text": "Hallo"}) in sup.sent


def test_status_file_is_technical_only(env):
    core_service = env.load("core_service")
    health = __import__("health")
    from hardware import InputEvent, SimulatedRinger
    core = core_service.Core(_Sup(), SimulatedRinger(), with_reminders=False)
    core.handle(InputEvent("hook_off"))           # a call is going on ...
    writer = core_service.StatusWriter(core, "web", "text", "ConsoleChannel")
    writer()
    raw = (env.output_dir / "core_status.json").read_text()
    assert "in_call" not in raw and "listening" not in raw   # ... and nobody can see it
    status = health.core_status()
    assert status["running"] is True and status["dialog"] == "bereit"
    assert status["dialog_restarts"] == 2 and status["last_restart"] == "llm_hang"
    assert health.core_status(now=time.time() + 60)["running"] is False


def test_supervisor_health_state_is_coarse(env):
    core_service = env.load("core_service")
    sup = core_service.DialogSupervisor(command=["true"])
    sup.proc = object()
    for state, expected in [("loading", "laedt"), ("thinking", "bereit"),
                            ("listening", "bereit"), ("ready", "bereit")]:
        sup.state = state
        assert sup.health_state() == expected
    sup.proc = None
    assert sup.health_state() == "neustart"


# --- device API: /v1/health -------------------------------------------------

def test_health_is_for_admin_only_and_has_no_content(env, monkeypatch):
    env.set(LLM_API_BASE="http://127.0.0.1:9/v1")      # nothing listens: not reachable
    device_api = env.load("device_api")
    import metrics
    metrics.log_interaction("handset", stt_duration_ms=400, llm_duration_ms=1200,
                            tts_duration_ms=500, total_duration_ms=2100)
    server = device_api.make_server("127.0.0.1", 0, device_api.token_hash(TOKEN))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    device_api.grant("team", "Projektteam", "admin")
    device_api.grant("sandra", "Sandra Keller", "angehoerige")
    base = f"http://127.0.0.1:{server.server_address[1]}"

    def get(person):
        req = urllib.request.Request(base + "/v1/health")
        req.add_header("Authorization", f"Bearer {TOKEN}")
        req.add_header("X-Person-Id", person)
        try:
            with _opener().open(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())
    try:
        assert get("sandra")[0] == 403
        status, body = get("team")
    finally:
        server.shutdown()
        server.server_close()
    assert status == 200
    assert set(body) == {"device", "services", "ai", "latency_target_ms", "daily"}
    assert body["ai"]["on_device"] is True and body["ai"]["reachable"] is False
    assert body["ai"]["cloud_allowed"] is False
    assert body["services"]["core"]["running"] is False      # no core in this test
    assert body["daily"][0]["llm_ms"]["p50"] == 1200


def test_health_never_contacts_an_outside_llm(env, monkeypatch):
    env.set(LLM_API_BASE="https://api.example.com/v1", ALLOW_CLOUD_LLM="true")
    health = env.load("health")
    monkeypatch.setattr(health.urllib.request, "build_opener",
                        lambda *a: pytest.fail("must not call an outside server"))
    info = health.ai_info()
    assert info["on_device"] is False and info["reachable"] is None
