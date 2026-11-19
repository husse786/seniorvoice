"""Button "Sprechen" (decided 19.11.2026): the device stops talking at once
and listens; after a quiet spell it first says where the conversation was."""

import socket
import subprocess
import sys
import time
import types


def _service(env):
    env.load("main")
    dialog = __import__("dialog_service")
    bus_mod = __import__("bus")
    core_end, dialog_end = socket.socketpair()
    return dialog, dialog.DialogService(bus_mod.Bus(dialog_end))


def test_press_while_speaking_stops_playback_and_mutes_rest(env, monkeypatch):
    env.load("config")
    sys.modules.pop("tts", None)
    tts = __import__("tts")
    monkeypatch.setattr(tts, "player_command", lambda path, output="handset": ["sleep", "5"])
    monkeypatch.setattr(tts, "synthesize", lambda text: __import__("pathlib").Path("/tmp/none.wav"))
    import threading
    t0 = time.monotonic()
    threading.Timer(0.3, tts.interrupt).start()
    tts.speak("Ein langer Satz")
    assert time.monotonic() - t0 < 3                       # stopped, not 5 s
    shown = []
    import sim_text
    sim_text.set_sink(lambda text, output: shown.append((output, text)))
    try:
        tts.speak("Der Rest der Antwort")                  # muted until resume()
        assert shown == []
        tts.speak("Bitte Hörer abheben", output="speaker")  # room speaker never muted
        assert shown == [("speaker", "Bitte Hörer abheben")]
    finally:
        sim_text.set_sink(None)
        tts.resume()
    assert not tts.interrupted()


def test_press_only_interrupts_while_talking_or_thinking(env, monkeypatch):
    dialog, s = _service(env)
    calls = []
    tts = types.ModuleType("tts")
    tts.interrupt = lambda: calls.append("interrupt")
    monkeypatch.setitem(sys.modules, "tts", tts)
    s.on_message({"type": "button", "name": "sprechen"})
    assert calls == [] and not s.talk_pressed               # no call: nothing
    s.call_active.set()
    s.current_state = "listening"
    s.on_message({"type": "button", "name": "sprechen"})
    assert calls == [] and s.talk_pressed                   # already listening: keep the sentence
    s.current_state = "speaking"
    s.on_message({"type": "button", "name": "sprechen"})
    assert calls == ["interrupt"]


def test_recap_quotes_last_words_without_llm(env):
    dialog, s = _service(env)
    assert s.recap([{"role": "assistant", "content": "Guten Tag"}]) is None
    text = s.recap([{"role": "user", "content": "Ich war heute auf dem Markt und habe Äpfel, "
                                                 "Birnen und sehr viel frisches Gemüse gekauft"},
                    {"role": "assistant", "content": "Schön!"}])
    assert text.startswith("Wo waren wir? Sie hatten gesagt: Ich war heute auf dem Markt")
    assert "…" in text and "Gemüse" not in text


def test_core_asks_to_lift_handset_when_hung_up(env):
    core_mod = env.load("core_service")
    assert "sprechen" in core_mod.HANDSET_BUTTONS


def test_new_call_is_never_muted_by_an_old_press(env, monkeypatch):
    dialog, s = _service(env)
    state = {"resumed": 0}
    tts = types.ModuleType("tts")
    tts.resume = lambda: state.__setitem__("resumed", state["resumed"] + 1)
    tts.speak = lambda text, output="handset": None
    monkeypatch.setitem(sys.modules, "tts", tts)
    s.talk_pressed = True
    monkeypatch.setattr(s, "open_call", lambda speak: [])
    s.call_active.clear()                     # hung up already: loop does not run
    s.run_call()
    assert state["resumed"] == 1 and not s.talk_pressed
