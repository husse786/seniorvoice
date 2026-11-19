"""Device screen (T11) and the simulation as a telephone: one screen page for
the Pi display and the drawn phone, typing and speaking at the same time,
sound chosen automatically. The conversation stays in RAM (A8)."""

import json
import queue
import sys
import types
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from conftest import patch_http

ZH = ZoneInfo("Europe/Zurich")


def _opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _get(url, host=None):
    req = urllib.request.Request(url)
    if host:
        req.add_header("Host", host)
    try:
        with _opener().open(req, timeout=5) as r:
            return r.status, r.read().decode(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), dict(e.headers)


def _screen(env, phone=None, now=None, **kw):
    screen = env.load("screen")
    state = phone if phone is not None else {"in_call": False}
    clock = {"t": 0.0}
    s = screen.Screen(lambda: dict(state), now=lambda: now or datetime.now(ZH),
                      monotonic=lambda: clock["t"], **kw)
    return screen, s, state, clock


# --- what the screen shows ---------------------------------------------------

def test_rest_shows_today_with_next_and_done(env):
    appointments = env.load("appointments")
    now = datetime(2026, 11, 19, 14, 0, tzinfo=ZH)
    for title, hour, kind in (("Blutdruck", 8, "medikament"), ("Coiffeur", 15, "termin"),
                              ("Abend-Tabletten", 18, "medikament")):
        appointments.add_appointment(title, datetime(2026, 11, 19, hour, 0), "test", kind=kind,
                                     now=now - timedelta(hours=8))
    appointments.add_appointment("Hausarzt", datetime(2026, 11, 20, 10, 0), "test", now=now)
    _, s, _, _ = _screen(env, now=now)
    state = s.state()
    assert state["modus"] == "ruhe"
    assert [(i["zeit"], i["titel"], i["vorbei"], i["naechster"]) for i in state["heute"]] == [
        ("08:00", "Blutdruck", True, False), ("15:00", "Coiffeur", False, True),
        ("18:00", "Abend-Tabletten", False, False)]
    assert state["morgen"] == "10:00 Hausarzt"


def test_modes_and_reminder_text(env):
    phone = {"in_call": False, "ringing": True, "help_open": False}
    _, s, state, _ = _screen(env, phone, ringing_text=lambda: "Guten Tag. Eine Erinnerung: Um 15:30 Uhr haben Sie Coiffeur.",
                             help_status=lambda: {"kontakt": "Sandra", "rolle": "Tochter", "zugestellt": True})
    got = s.state()
    assert got["modus"] == "klingelt" and got["erinnerung"] == "Eine Erinnerung: Um 15:30 Uhr haben Sie Coiffeur."
    state.update(ringing=False, in_call=True)
    assert s.state()["modus"] == "gespraech"
    state.update(help_open=True)
    got = s.state()
    assert got["modus"] == "hilfe" and got["hilfe"]["kontakt"] == "Sandra"


def test_conversation_only_during_call_and_gone_after_hang_up(env):
    phone = {"in_call": True}
    _, s, state, _ = _screen(env, phone)
    s.show("Guten Tag, Frau Keller.", "handset")
    s.show("Bitte heben Sie ab.", "speaker")          # room speaker: not the conversation
    s.heard("Ja, eine Suppe")
    assert [(l["who"], l["text"]) for l in s.state()["gespraech"]] == [
        ("geraet", "Guten Tag, Frau Keller."), ("senior", "Ja, eine Suppe")]
    s.forget()
    assert s.state()["gespraech"] == []
    s.heard("noch etwas")
    state["in_call"] = False
    assert s.state()["gespraech"] == []                # never shown while hung up


def test_core_feeds_screen_and_clears_it_on_hang_up(env):
    core_mod = env.load("core_service")
    hw = __import__("hardware")

    class Sup:
        on_restart = on_ready = None
        def send(self, kind, **kw): return True
        def check(self): pass
        def health_state(self): return "bereit"
    core = core_mod.Core(Sup(), hw.SimulatedRinger(), with_reminders=False)
    screen = __import__("screen")
    core.screen = screen.Screen(core.phone_state)
    core.handle(hw.InputEvent("hook_off"))
    core.handle(hw.InputEvent("sim_text", "getippt"))
    assert core.screen.state()["gespraech"] == [{"who": "senior", "text": "getippt"}]
    core.handle(hw.InputEvent("hook_on"))
    core.handle(hw.InputEvent("hook_off"))
    assert core.screen.state()["gespraech"] == []


# --- the screen page ---------------------------------------------------------

def test_screen_server_serves_page_and_state_on_localhost_only(env):
    screen, s, _, _ = _screen(env)
    server = screen.ScreenServer(s, 0)
    server.start()
    try:
        base = f"http://127.0.0.1:{server.server.server_address[1]}"
        status, page, headers = _get(base + "/")
        assert status == 200 and "Gespräch läuft" in page
        assert "frame-ancestors 'self'" in headers["Content-Security-Policy"]
        status, body, _ = _get(base + "/screen/state")
        assert status == 200 and json.loads(body)["modus"] == "ruhe"
        assert _get(base + "/screen/state", host="evil.example")[0] == 403
        assert server.server.server_address[0] == "127.0.0.1"
    finally:
        server.stop()


def test_phone_page_shows_screen_and_accepts_typing_in_audio_mode(env):
    sim_phone = env.load("sim_phone")
    screen = __import__("screen")
    state = {"in_call": True}
    p = sim_phone.SimPhone(0, state=lambda: dict(state), text_mode=False)
    p.screen = screen.Screen(lambda: dict(state))
    events = queue.Queue()
    p.start(events)
    try:
        base = f"http://127.0.0.1:{p.server.server_address[1]}"
        status, page, _ = _get(base + "/")
        assert status == 200 and 'src="/screen"' in page and "Tippen statt sprechen" in page
        assert _get(base + "/screen")[0] == 200
        assert p.say("Wie wird das Wetter?") is None          # audio mode: typing still works
        assert events.get_nowait().kind == "sim_text"
        p.heard("gesprochen ins Mikrofon")
        assert [l["label"] for l in p.lines()] == ["getippt", "gesprochen"]
        p.forget_conversation()
        assert p.lines() == []
    finally:
        p.stop()


def test_phone_page_times_are_swiss(env):
    sim_phone = env.load("sim_phone")
    p = sim_phone.SimPhone(0)
    p.show("Hallo")
    expected = datetime.now(ZH).strftime("%H:%M")
    assert p.lines()[0]["t"].startswith(expected)


# --- typing while the microphone is on ---------------------------------------

def test_typed_text_replaces_speaking_in_audio_mode(env, monkeypatch):
    main = env.load("main")
    calls = []
    audio = types.ModuleType("audio_capture")
    audio.record_until_silence = lambda: calls.append("record") or b"RIFF"
    stt = types.ModuleType("stt")
    stt.transcribe = lambda wav: calls.append("stt") or "gesprochen"
    tts = types.ModuleType("tts")
    tts.speak = lambda text, output="handset": None
    for name, mod in (("audio_capture", audio), ("stt", stt), ("tts", tts)):
        monkeypatch.setitem(sys.modules, name, mod)
    import llm_backend

    def llm(req, timeout=None):
        body = json.dumps({"choices": [{"message": {"content": "Gut."}}]}).encode()
        return type("R", (), {"read": lambda self: body, "__enter__": lambda self: self,
                              "__exit__": lambda self, *a: False})()
    patch_http(llm_backend, monkeypatch, llm)
    import sim_text
    sim_text.put_input("getippt")
    history, _ = main.run_pipeline(use_pir=False, history=[], trigger="handset")
    assert calls == [] and history[0]["content"] == "getippt"
    heard = []
    sim_text.set_heard_sink(heard.append)
    try:
        history, _ = main.run_pipeline(use_pir=False, history=[], trigger="handset")
    finally:
        sim_text.set_heard_sink(None)
    assert calls == ["record", "stt"] and heard == ["gesprochen"]


# --- sound chosen automatically ----------------------------------------------

@pytest.fixture
def audio_env(env, monkeypatch, tmp_path):
    voice = tmp_path / "voice.onnx"
    voice.write_text("x")
    env.set(PIPER_VOICE=voice, AUDIO_DEVICE_NAME="C920")
    core = env.load("core_service")
    sd = types.ModuleType("sounddevice")
    sd.query_devices = lambda: [{"name": "MacBook Air Microphone", "max_input_channels": 1},
                                {"name": "MacBook Air Speakers", "max_input_channels": 0}]
    monkeypatch.setitem(sys.modules, "sounddevice", sd)
    monkeypatch.setattr(core.shutil, "which", lambda name: "/usr/bin/" + name)
    import importlib.util
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    monkeypatch.delenv("AUDIO_DEVICE_NAME", raising=False)
    import config
    monkeypatch.setattr(config, "AUDIO_DEVICE_NAME", "C920")
    return core, voice, monkeypatch


def test_mac_without_c920_uses_default_microphone(audio_env):
    core, _, monkeypatch = audio_env
    import os
    import config
    mode, note = core.resolve_sim_audio("auto")
    assert mode == "audio" and "Standard-Mikrofon" in note
    assert config.AUDIO_DEVICE_NAME == "" and os.environ["AUDIO_DEVICE_NAME"] == ""


def test_missing_voice_falls_back_to_typing_with_reason(audio_env):
    core, voice, _ = audio_env
    voice.unlink()
    mode, note = core.resolve_sim_audio("auto")
    assert mode == "text" and "Piper" in note and "Tippen geht" in note


def test_text_can_still_be_forced(audio_env):
    core, _, _ = audio_env
    assert core.resolve_sim_audio("text")[0] == "text"


def test_silent_microphone_gives_hint(env):
    env.load("config")
    sim_text = env.load("sim_text")
    shown = []
    sim_text.set_sink(lambda text, output: shown.append((output, text)))
    try:
        sys.modules.pop("audio_capture", None)
        sd = types.ModuleType("sounddevice")
        sys.modules.setdefault("sounddevice", sd)
        audio = __import__("audio_capture")
        audio._level_hint(0.0)
        audio._level_hint(0.5)
    finally:
        sim_text.set_sink(None)
    assert len(shown) == 1 and shown[0][0] == "hinweis" and "Mikrofon" in shown[0][1]
