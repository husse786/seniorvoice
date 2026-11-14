"""Dialog process: one call = turns until hang-up; reports state to the core."""

import socket
import sys
import types

from conftest import patch_http


def _setup(env, monkeypatch, sentence, llm):
    env.load("main")
    dialog = __import__("dialog_service")
    bus_mod = __import__("bus")
    core_end, dialog_end = socket.socketpair()
    service = dialog.DialogService(bus_mod.Bus(dialog_end))
    core_bus = bus_mod.Bus(core_end)

    spoken = []
    audio = types.ModuleType("audio_capture")
    audio.record_until_silence = lambda: b"RIFF"
    stt = types.ModuleType("stt")
    stt.transcribe = lambda wav: sentence
    tts = types.ModuleType("tts")

    def speak(text):
        spoken.append(text)
        service.call_active.clear()   # senior hangs up after the first answer
    tts.speak = speak
    for name, mod in [("audio_capture", audio), ("stt", stt), ("tts", tts)]:
        monkeypatch.setitem(sys.modules, name, mod)

    import llm_backend
    patch_http(llm_backend, monkeypatch, llm)
    return service, core_bus, spoken, dialog


def _states(core_bus):
    core_bus._sock.settimeout(0.5)
    states = []
    while True:
        try:
            msg = core_bus.receive()
        except Exception:
            break
        if msg is None:
            break
        states.append(msg.get("state"))
    return states


def test_llm_failure_gets_spoken_apology_and_idle_state(env, monkeypatch):
    def broken(req, timeout=None):
        raise OSError("ollama down")
    service, core_bus, spoken, dialog = _setup(env, monkeypatch, "Wie ist das Wetter", broken)
    service.call_active.set()
    service.run_call()
    assert spoken == [dialog.LLM_FAILED_REPLY]
    states = _states(core_bus)
    assert "thinking" in states and states[-1] == "idle"


def test_hang_up_during_transcription_sends_nothing_to_llm(env, monkeypatch):
    calls = []

    def llm(req, timeout=None):
        calls.append(1)
        raise OSError("must not be called")
    service, core_bus, spoken, dialog = _setup(env, monkeypatch, "Hallo", llm)
    stt = sys.modules["stt"]

    def transcribe_then_hang_up(wav):
        service.call_active.clear()
        return "Hallo"
    stt.transcribe = transcribe_then_hang_up
    service.call_active.set()
    service.run_call()
    assert calls == [] and spoken == []


def test_ping_is_answered(env, monkeypatch):
    service, core_bus, _, _ = _setup(env, monkeypatch, "", lambda r, timeout=None: None)
    service.on_message({"type": "ping"})
    assert core_bus.receive() == {"type": "pong"}
