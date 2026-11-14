"""Streaming answers: watchdog sees 'speaking' during playback; hang-up stops speech."""

import sys
import types


def _load(env, monkeypatch, tokens):
    env.load("main")
    llm_client = __import__("llm_client")
    spoken = []
    tts = types.ModuleType("tts")
    tts.speak = spoken.append
    monkeypatch.setitem(sys.modules, "tts", tts)
    closed = []

    def stream(messages):
        try:
            for t in tokens:
                yield t
        finally:
            closed.append(True)
    monkeypatch.setattr(llm_client, "llm_stream", stream)
    return llm_client, spoken, closed


def test_states_around_each_sentence(env, monkeypatch):
    llm_client, spoken, _ = _load(env, monkeypatch, ["Guten ", "Tag. ", "Wie ", "geht ", "es?"])
    states = []
    llm_client.chat_streaming("Hallo", [], on_state=states.append)
    assert spoken == ["Guten Tag.", "Wie geht es?"]
    assert states == ["speaking", "thinking", "speaking", "thinking"]


def test_hang_up_stops_speaking_and_closes_stream(env, monkeypatch):
    llm_client, spoken, closed = _load(env, monkeypatch, ["Eins. ", "Zwei. ", "Drei."])
    active = {"on": True}

    def speak_then_hang_up(text):
        spoken.append(text)
        active["on"] = False
    sys.modules["tts"].speak = speak_then_hang_up
    llm_client.chat_streaming("Hallo", [], still_active=lambda: active["on"])
    assert spoken == ["Eins."] and closed == [True]


def test_non_streaming_answer_not_spoken_after_hang_up(env, monkeypatch):
    main = env.load("main")
    spoken = []
    active = {"on": True}
    for name, attrs in {
        "audio_capture": {"record_until_silence": lambda: b"RIFF"},
        "stt": {"transcribe": lambda wav: "Hallo"},
        "tts": {"speak": spoken.append},
    }.items():
        mod = types.ModuleType(name)
        for k, v in attrs.items():
            setattr(mod, k, v)
        monkeypatch.setitem(sys.modules, name, mod)
    import llm_client

    def chat(text, history, facts_block=""):
        active["on"] = False                 # hung up while the LLM was thinking
        return "Antwort", history
    monkeypatch.setattr(llm_client, "chat", chat)
    monkeypatch.setattr(main, "LLM_STREAM", False)
    main.run_pipeline(False, [], trigger="handset", still_active=lambda: active["on"])
    assert spoken == []
