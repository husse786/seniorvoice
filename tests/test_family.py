"""Decision A4/M7/D8: family message only after read-back and a clear yes."""

import socket
import sys
import types
from datetime import datetime, timedelta, timezone

import pytest


def _dialog(env, monkeypatch, transcripts):
    env.load("main")
    dialog = __import__("dialog_service")
    bus_mod = __import__("bus")
    help_mod = __import__("help_alert")
    help_mod.set_contacts([
        {"name": "Spitex", "role": "Spitex", "address": "spx"},
        {"name": "Sandra", "role": "Tochter", "address": "chat-sandra"},
    ])
    a, b = socket.socketpair()
    service = dialog.DialogService(bus_mod.Bus(b))
    it = iter(transcripts)
    spoken = []
    audio = types.ModuleType("audio_capture")
    audio.record_until_silence = lambda: b"RIFF"
    stt = types.ModuleType("stt")
    stt.transcribe = lambda wav: next(it)
    tts = types.ModuleType("tts")
    tts.speak = spoken.append
    tts.play = lambda p: None
    for name, mod in [("audio_capture", audio), ("stt", stt), ("tts", tts)]:
        monkeypatch.setitem(sys.modules, name, mod)
    service.call_active.set()
    return service, spoken


def test_message_sent_only_after_yes(env, monkeypatch):
    service, spoken = _dialog(env, monkeypatch, ["Ich komme am Sonntag zum Essen", "Ja"])
    service.family_message()
    family = sys.modules["family"]
    assert spoken[1] == ("Ich habe verstanden: Ich komme am Sonntag zum Essen. "
                         "Soll ich das an Sandra senden? Bitte sagen Sie Ja oder Nein.")
    assert spoken[-1] == "In Ordnung. Ich sende die Nachricht an Sandra."
    assert [m["status"] for m in family.list_outbox()] == ["wartet"]


def test_unclear_answer_sends_nothing(env, monkeypatch):
    service, spoken = _dialog(env, monkeypatch, ["Bring Milch mit", "Hm, ich weiss nicht"])
    service.family_message()
    assert spoken[-1] == "In Ordnung, ich sende nichts."
    assert sys.modules["family"].list_outbox() == []


def test_sending_removes_text_keeps_status(env, monkeypatch):
    service, _ = _dialog(env, monkeypatch, ["Familientext Geheim77", "Ja gerne"])
    service.family_message()
    family = sys.modules["family"]
    channels = __import__("channels")
    channel = channels.ConsoleChannel()
    assert family.send_pending(channel) == 1
    assert channel.sent[0][0] == "chat-sandra" and "Geheim77" in channel.sent[0][1]
    assert family.list_outbox()[0] == {"id": 1, "name": "Sandra", "text": "", "status": "gesendet"}
    assert env.files_containing("Geheim77") == []


def test_unsent_text_deleted_after_7_days(env, monkeypatch):
    service, _ = _dialog(env, monkeypatch, ["Unsent Geheim88", "Ja"])
    service.family_message()
    family = sys.modules["family"]
    now = datetime.now(timezone.utc)
    assert family.purge_expired(now + timedelta(days=6)) == 0
    assert family.purge_expired(now + timedelta(days=7, minutes=1)) == 1
    assert env.files_containing("Geheim88") == []


def test_family_button_without_handset_asks_to_lift(env):
    core_mod = env.load("core_service")
    hw = __import__("hardware")
    said, sent = [], []

    class Sup:
        on_restart = None

        def send(self, kind, **kw):
            sent.append(kind)

        def check(self):
            pass
    core = core_mod.Core(Sup(), hw.SimulatedRinger(), announce=said.append, with_reminders=False)
    core.handle(hw.InputEvent("button", "familie"))
    assert said and "heben Sie zuerst den Hörer ab" in said[0] and sent == []
    core.handle(hw.InputEvent("hook_off"))
    core.handle(hw.InputEvent("button", "familie"))
    assert sent == ["call_start", "button"]


def test_hang_up_during_confirmation_says_and_sends_nothing(env, monkeypatch):
    service, spoken = _dialog(env, monkeypatch, ["Bring Brot", "Ja"])
    stt = sys.modules["stt"]
    answers = iter(["Bring Brot", "Ja"])

    def transcribe(wav):
        text = next(answers)
        if text == "Ja":
            service.call_active.clear()            # hung up while confirming
        return text
    stt.transcribe = transcribe
    service.family_message()
    assert sys.modules["family"].list_outbox() == []
    assert not any("sende" in s for s in spoken[2:])


def test_family_button_mid_turn_keeps_words_from_llm(env, monkeypatch):
    service, spoken = _dialog(env, monkeypatch, [])
    import llm_backend
    from conftest import patch_http
    calls = []
    patch_http(llm_backend, monkeypatch, lambda req, timeout=None: calls.append(1))
    stt = sys.modules["stt"]
    answers = iter(["Was ich eigentlich der Familie sagen wollte", "Komme Sonntag", "Ja"])

    def transcribe(wav):
        text = next(answers, "")
        if text.startswith("Was ich"):
            service.on_message({"type": "button", "name": "familie"})   # pressed mid-turn
        if text == "Ja":
            service.call_active.clear()
            service.call_active.set()
        return text
    stt.transcribe = transcribe

    def speak(text):
        spoken.append(text)
        if text.startswith("In Ordnung. Ich sende"):
            service.call_active.clear()
    sys.modules["tts"].speak = speak
    service.on_message({"type": "call_start"})
    service.run_call()
    assert calls == []
    assert [m["status"] for m in sys.modules["family"].list_outbox()] == ["wartet"]


def test_expired_message_is_never_sent(env, monkeypatch):
    service, _ = _dialog(env, monkeypatch, ["Alt", "Ja"])
    service.family_message()
    family = sys.modules["family"]
    channel = __import__("channels").ConsoleChannel()
    later = datetime.now(timezone.utc) + timedelta(days=8)   # device was offline a week
    assert family.send_pending(channel, now=later) == 0
    assert channel.sent == []
