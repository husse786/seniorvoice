"""Decision A8 / F1: no conversation text in log files, database or audio files.

The end-to-end test runs one pipeline turn with fake audio, STT, LLM and TTS,
then searches every file the pipeline wrote (log files, SQLite DB, WAL, SHM)
for the spoken test sentence and the answer.
"""

import io
import json
import sys
import types

from conftest import patch_http

USER_SENTENCE = "Mein Blutdruck ist heute 180 zu 110 Testsatz4711"
ANSWER = "Bitte rufen Sie Ihre Hausaerztin an Antwortsatz0815"


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _silent_wav() -> bytes:
    import wave
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 1600)
    return buf.getvalue()


def _install_fakes(monkeypatch, spoken):
    """Fake hardware and models; the real stt.py wrapper is used (with a fake Whisper)."""
    audio = types.ModuleType("audio_capture")
    audio.record_until_silence = _silent_wav

    class FakeWhisper:
        def __init__(self, *a, **k):
            pass

        def transcribe(self, audio, **kwargs):
            seg = types.SimpleNamespace(text=USER_SENTENCE)
            info = types.SimpleNamespace(language="de", language_probability=0.98)
            return [seg], info

    faster_whisper = types.ModuleType("faster_whisper")
    faster_whisper.WhisperModel = FakeWhisper
    tts = types.ModuleType("tts")
    tts.speak = lambda text: spoken.append(text)
    tts.play = lambda path, output="handset": None
    for name, mod in [("audio_capture", audio), ("faster_whisper", faster_whisper), ("tts", tts)]:
        monkeypatch.setitem(sys.modules, name, mod)
    sys.modules.pop("stt", None)  # import the real stt.py with the fake model
    monkeypatch.setattr("builtins.input", lambda *a: "")


def _run_one_turn(env, monkeypatch, **extra_env):
    env.set(LOG_LEVEL="DEBUG", **extra_env)
    main = env.load("main")
    spoken = []
    _install_fakes(monkeypatch, spoken)

    import llm_backend

    def urlopen(req, timeout=None):
        body = {"choices": [{"message": {"content": ANSWER}}]}
        return _FakeResponse(json.dumps(body).encode("utf-8"))

    patch_http(llm_backend, monkeypatch, urlopen)

    main.run_legacy_purge()
    history, _ = main.run_pipeline(use_pir=False, history=[])
    for handler in __import__("logging").getLogger().handlers:
        handler.flush()
    return history, spoken


def test_turn_leaves_no_text_in_files(env, monkeypatch):
    history, spoken = _run_one_turn(env, monkeypatch)

    # The turn really happened (in RAM)
    assert spoken == [ANSWER]
    assert history[-2]["content"] == USER_SENTENCE

    # ...but nothing of it is on disk
    assert env.files_containing("Testsatz4711") == []
    assert env.files_containing("Antwortsatz0815") == []

    # Metrics are still recorded for Grafana, in their own file
    import sqlite3
    conn = sqlite3.connect(env.metrics_path)
    rows = conn.execute(
        "SELECT trigger_type, user_text, response_text, llm_duration_ms FROM interactions"
    ).fetchall()
    conn.close()
    assert len(rows) == 1
    trigger, user_text, response_text, llm_ms = rows[0]
    assert (trigger, user_text, response_text) == ("keyboard", "", "")
    assert llm_ms is not None


def test_content_log_goes_to_console_only(env, monkeypatch, capsys):
    _run_one_turn(env, monkeypatch, LOG_CONTENT="true")
    out = capsys.readouterr().out
    assert "Testsatz4711" in out          # visible for development
    assert env.files_containing("Testsatz4711") == []   # never in a file


def test_content_hidden_from_console_by_default(env, monkeypatch, capsys):
    _run_one_turn(env, monkeypatch)
    out = capsys.readouterr().out
    assert "Testsatz4711" not in out
    assert "Antwortsatz0815" not in out


def test_tts_audio_deleted_after_playback(env, monkeypatch):
    tts = env.load("tts")

    def fake_run(cmd, input=None, **kwargs):
        out = cmd[cmd.index("--output_file") + 1]
        with open(out, "wb") as fh:
            fh.write(b"RIFF" + input.encode("utf-8"))
        return types.SimpleNamespace(returncode=0, stderr="")

    played = []
    monkeypatch.setattr(tts.shutil, "which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(tts.subprocess, "run", fake_run)
    monkeypatch.setattr(tts, "play", lambda path, output="handset": played.append(path.exists()))

    tts.speak(ANSWER)
    assert played == [True]
    assert list(env.output_dir.glob("*.wav")) == []


def test_tts_audio_deleted_when_playback_fails(env, monkeypatch):
    tts = env.load("tts")

    def fake_run(cmd, input=None, **kwargs):
        out = cmd[cmd.index("--output_file") + 1]
        open(out, "wb").write(b"RIFF")
        return types.SimpleNamespace(returncode=0, stderr="")

    def broken_play(path, output="handset"):
        raise RuntimeError("no speaker")

    monkeypatch.setattr(tts.shutil, "which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(tts.subprocess, "run", fake_run)
    monkeypatch.setattr(tts, "play", broken_play)
    try:
        tts.speak(ANSWER)
    except RuntimeError:
        pass
    assert list(env.output_dir.glob("*.wav")) == []


def test_default_audio_dir_is_ram(env, monkeypatch):
    monkeypatch.delenv("OUTPUT_DIR")
    config = env.load("config")
    from pathlib import Path
    if Path("/dev/shm").is_dir():
        assert str(config.OUTPUT_DIR).startswith("/dev/shm")
