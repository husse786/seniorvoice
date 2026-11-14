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


def test_new_call_during_old_turn_does_not_continue_old_one(env, monkeypatch):
    calls = []

    def llm(req, timeout=None):
        calls.append(1)
        raise OSError("must not be called")
    service, core_bus, spoken, dialog = _setup(env, monkeypatch, "Hallo", llm)

    def transcribe_hang_up_and_lift_again(wav):
        service.on_message({"type": "call_end"})
        service.on_message({"type": "call_start"})
        return "Hallo"
    sys.modules["stt"].transcribe = transcribe_hang_up_and_lift_again
    service.on_message({"type": "call_start"})
    service.run_call()                       # old call returns at once
    assert calls == [] and spoken == []
    assert service.call_active.is_set()      # new call is still on


def test_facts_reloaded_after_forget_all(env, monkeypatch):
    service, core_bus, spoken, dialog = _setup(env, monkeypatch, "Vergiss alles",
                                               lambda r, timeout=None: None)
    main = sys.modules["main"]
    loads = []
    real = main._reload_facts
    monkeypatch.setattr(main, "_reload_facts", lambda: (loads.append(1), real())[1])
    service.on_message({"type": "call_start"})
    service.run_call()
    assert len(loads) >= 2                   # once at start, once after the forget turn


def test_silence_ends_conversation_after_timeout(env, monkeypatch):
    import json
    answers = iter(["Ich heisse Anna", "", ""])
    service, core_bus, spoken, dialog = _setup(env, monkeypatch, "", None)
    sys.modules["stt"].transcribe = lambda wav: next(answers, "")
    sys.modules["tts"].speak = lambda text: spoken.append(text)

    def llm(req, timeout=None):
        body = json.dumps({"choices": [{"message": {"content": "Guten Tag Anna."}}]}).encode()
        class R:
            def read(self): return body
            def __enter__(self): return self
            def __exit__(self, *a): return False
        return R()
    import llm_backend
    patch_http(llm_backend, monkeypatch, llm)
    import config
    monkeypatch.setattr(config, "MEMORY_TIMEOUT", 0)
    memory = sys.modules["memory"]
    extracted = []
    monkeypatch.setattr(memory, "extract_facts_async",
                        lambda history, source="": extracted.append((len(history), source)))
    turns = {"n": 0}
    main = sys.modules["main"]
    real = main.run_pipeline

    def counting(*a, **kw):
        turns["n"] += 1
        if turns["n"] >= 3:
            service.call_active.clear()
        return real(*a, **kw)
    counting.last_text = ""
    monkeypatch.setattr(main, "run_pipeline", counting)
    service.on_message({"type": "call_start"})
    service.run_call()
    assert extracted and extracted[0][1].startswith("timeout-")
    assert not any(src.startswith("call-") for _, src in extracted)   # history was emptied
