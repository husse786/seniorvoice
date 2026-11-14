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
