"""Decision A7: callback only after a clear yes, at most once a day, 1 retry, then 'nicht erreicht'."""

import sys
import types
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

ZH = ZoneInfo("Europe/Zurich")
NOW = datetime(2026, 11, 20, 15, 42, tzinfo=ZH).astimezone(timezone.utc)


@pytest.mark.parametrize("answer,expected", [
    ("Ja.", True), ("Ja, gerne!", True), ("Gerne", True), ("Jawohl", True),
    ("Nein", False), ("Ja, aber nicht morgen", False), ("Vielleicht", False),
    ("Ich weiss nicht", False), ("", False), ("Hm", False),
    ("Ja ich glaube schon wenn es geht", False),          # long and unclear
    ("Lieber nicht", False), ("Bitte", False),
])
def test_only_clear_yes_counts(env, answer, expected):
    cb = env.load("callback")
    assert cb.is_clear_yes(answer) is expected


def test_yes_schedules_callback_tomorrow(env):
    cb = env.load("callback")
    appts = sys.modules["appointments"]
    accepted, reply = cb.record_answer("Ja, gerne", NOW)
    assert accepted and reply == "Gerne. Ich rufe Sie morgen um 15:45 Uhr an. Auf Wiederhören."
    rows = appts.list_reminders()
    assert len(rows) == 1 and rows[0]["kind"] == "rueckruf" and rows[0]["stage"] == "main"
    assert rows[0]["created_by"] == "Senior (Ja am Telefon)"


def test_unclear_answer_schedules_nothing(env):
    cb = env.load("callback")
    accepted, reply = cb.record_answer("Ja, vielleicht", NOW)
    assert not accepted and reply == cb.CONFIRM_NO
    assert sys.modules["appointments"].list_reminders() == []


def test_asks_at_most_once_per_day(env):
    cb = env.load("callback")
    assert cb.may_offer(NOW)
    cb.record_answer("Nein", NOW)
    assert not cb.may_offer(NOW + timedelta(hours=5))
    assert cb.may_offer(NOW + timedelta(days=1))


def test_unanswered_callback_is_nicht_erreicht(env):
    cb = env.load("callback")
    appts = sys.modules["appointments"]
    cb.record_answer("Ja", NOW)
    clock = {"wall": NOW + timedelta(days=1, minutes=3), "mono": 0.0}

    class Ringer:
        ringing = False

        def ring(self):
            self.ringing = True

        def stop(self):
            self.ringing = False

    ringer = Ringer()
    sched = appts.ReminderScheduler(ringer, in_call=lambda: False,
                                    now=lambda: clock["wall"], monotonic=lambda: clock["mono"])

    def advance(seconds):
        clock["wall"] += timedelta(seconds=seconds)
        clock["mono"] += seconds

    sched.tick()
    assert ringer.ringing
    advance(60); sched.tick()            # no pickup
    advance(600); sched.tick()           # retry after 10 min
    assert ringer.ringing
    advance(60); sched.tick()
    assert appts.list_reminders()[0]["status"] == "nicht erreicht"


def test_cancel_by_voice(env):
    cb = env.load("callback")
    cb.record_answer("Ja", NOW)
    assert cb.is_cancel_request("Rufen Sie mich bitte nicht an")
    assert cb.is_cancel_request("Bitte den Anruf absagen")
    assert not cb.is_cancel_request("Meine Tochter ruft mich an")
    assert cb.cancel_open_callbacks() == 1
    assert sys.modules["appointments"].list_reminders() == []


@pytest.mark.parametrize("text,expected", [
    ("Danke, tschüss", True), ("Auf Wiederhören!", True), ("Gute Nacht", True),
    ("Wie spät ist es?", False), ("Ich habe Tschüssi gesagt", False),
])
def test_goodbye_detection(env, text, expected):
    cb = env.load("callback")
    assert cb.is_goodbye(text) is expected


def test_dialog_offers_callback_after_goodbye(env, monkeypatch):
    """End to end in the dialog process, LLM faked."""
    import io, json, socket
    from conftest import patch_http
    env.load("main")
    dialog = __import__("dialog_service")
    bus_mod = __import__("bus")
    a, b = socket.socketpair()
    service = dialog.DialogService(bus_mod.Bus(b))
    transcripts = iter(["Danke für das Gespräch, tschüss", "Ja gerne"])
    spoken = []
    audio = types.ModuleType("audio_capture")
    audio.record_until_silence = lambda: b"RIFF"
    stt = types.ModuleType("stt")
    stt.transcribe = lambda wav: next(transcripts)
    tts = types.ModuleType("tts")

    def speak(text):
        spoken.append(text)
        if text.startswith("Gerne. Ich rufe"):
            service.call_active.clear()
    tts.speak = speak
    for name, mod in [("audio_capture", audio), ("stt", stt), ("tts", tts)]:
        monkeypatch.setitem(sys.modules, name, mod)

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *e):
            return False
    import llm_backend
    patch_http(llm_backend, monkeypatch, lambda req, timeout=None: Resp(
        json.dumps({"choices": [{"message": {"content": "Auf Wiederhören."}}]}).encode()))

    service.call_active.set()
    service.run_call()
    assert spoken[0] == "Auf Wiederhören."
    assert spoken[1].startswith("Darf ich Sie morgen um")
    assert spoken[2].startswith("Gerne. Ich rufe Sie morgen um")
    assert [r["kind"] for r in sys.modules["appointments"].list_reminders()] == ["rueckruf"]


def test_cancel_also_removes_callback_waiting_for_retry(env):
    cb = env.load("callback")
    appts = sys.modules["appointments"]
    cb.record_answer("Ja", NOW)
    clock = {"wall": NOW + timedelta(days=1, minutes=3), "mono": 0.0}

    class Ringer:
        def ring(self): pass
        def stop(self): pass
    sched = appts.ReminderScheduler(Ringer(), in_call=lambda: False,
                                    now=lambda: clock["wall"], monotonic=lambda: clock["mono"])
    sched.tick()                                   # first attempt
    clock["wall"] += timedelta(seconds=60); clock["mono"] += 60
    sched.tick()                                   # unanswered, retry pending
    assert appts.list_reminders()[0]["status"] == "klingelt"
    assert cb.cancel_open_callbacks() == 1
    assert appts.list_reminders() == []


def _offer_dialog(env, monkeypatch, on_record):
    import socket
    env.load("main")
    dialog = __import__("dialog_service")
    bus_mod = __import__("bus")
    a, b = socket.socketpair()
    service = dialog.DialogService(bus_mod.Bus(b))
    spoken = []
    audio = types.ModuleType("audio_capture")
    audio.record_until_silence = lambda: on_record(service)
    stt = types.ModuleType("stt")
    stt.transcribe = lambda wav: "Ja"
    tts = types.ModuleType("tts")
    tts.speak = spoken.append
    for name, mod in [("audio_capture", audio), ("stt", stt), ("tts", tts)]:
        monkeypatch.setitem(sys.modules, name, mod)
    service.on_message({"type": "call_start"})
    return service, spoken


def test_yes_after_hang_up_schedules_nothing(env, monkeypatch):
    def hang_up_while_answering(service):
        service.on_message({"type": "call_end"})
        return b"RIFF"
    service, spoken = _offer_dialog(env, monkeypatch, hang_up_while_answering)
    service.offer_callback()
    assert sys.modules["appointments"].list_reminders() == []
    assert len(spoken) == 1                        # only the question


def test_failed_recording_still_counts_as_asked_today(env, monkeypatch):
    def broken(service):
        raise OSError("microphone gone")
    service, spoken = _offer_dialog(env, monkeypatch, broken)
    with pytest.raises(OSError):
        service.offer_callback()
    assert not sys.modules["callback"].may_offer(datetime.now(timezone.utc))
