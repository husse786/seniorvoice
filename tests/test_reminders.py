"""Decisions A5, A6, B2, B5, A8: reminders ring like a phone, 2 attempts, then 'verpasst'."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

ZH = ZoneInfo("Europe/Zurich")
T0 = datetime(2026, 11, 20, 13, 0, tzinfo=ZH)        # "now" = 13:00 local


class Clock:
    def __init__(self):
        self.wall = T0.astimezone(timezone.utc)
        self.mono = 1000.0

    def advance(self, **kw):
        delta = timedelta(**kw)
        self.wall += delta
        self.mono += delta.total_seconds()


class FakeRinger:
    def __init__(self):
        self.ringing = False
        self.rings = 0

    def ring(self):
        self.ringing = True
        self.rings += 1

    def stop(self):
        self.ringing = False


@pytest.fixture
def setup(env):
    appts = env.load("appointments")
    clock = Clock()
    ringer = FakeRinger()
    state = {"in_call": False}
    sched = appts.ReminderScheduler(
        ringer, in_call=lambda: state["in_call"],
        now=lambda: clock.wall, monotonic=lambda: clock.mono,
    )
    return appts, clock, ringer, sched, state


def _status(appts, stage="main"):
    return [r for r in appts.list_reminders() if r["stage"] == stage][0]


def test_rings_on_time_and_announces_on_pickup(setup):
    appts, clock, ringer, sched, _ = setup
    appts.add_appointment("Arzttermin bei Dr. Meier", T0.replace(hour=14), "Spitex",
                          now=clock.wall)
    clock.advance(minutes=30)               # 13:30 = pre-reminder
    sched.tick()
    assert ringer.ringing
    text = sched.on_hook_off()
    assert text == "Guten Tag. Eine Erinnerung: Um 14:00 Uhr haben Sie Arzttermin bei Dr. Meier."
    assert _status(appts, "pre")["status"] == "bestaetigt"

    clock.advance(minutes=30, seconds=59)   # 14:00:59: at most 1 min late
    sched.tick()
    assert ringer.ringing
    assert "Jetzt, um 14:00 Uhr" in sched.on_hook_off()


def test_two_attempts_then_verpasst(setup):
    appts, clock, ringer, sched, _ = setup
    appts.add_appointment("Podologie", T0.replace(hour=13, minute=10), "Tochter",
                          pre_minutes=0, now=clock.wall)
    clock.advance(minutes=10)
    sched.tick()
    assert ringer.ringing and _status(appts)["attempts"] == 1
    clock.advance(seconds=60)
    sched.tick()                             # nobody picked up
    assert not ringer.ringing and _status(appts)["status"] == "klingelt"

    clock.advance(minutes=9)
    sched.tick()
    assert not ringer.ringing                # not before 10 minutes
    clock.advance(minutes=1)
    sched.tick()
    assert ringer.ringing and _status(appts)["attempts"] == 2
    clock.advance(seconds=60)
    sched.tick()
    assert _status(appts)["status"] == "verpasst"
    clock.advance(minutes=30)
    sched.tick()
    assert ringer.rings == 2                 # no third attempt, no escalation (A6)


def test_medication_text_verbatim_and_no_pre_reminder(setup):
    appts, clock, ringer, sched, _ = setup
    appts.add_appointment("1 Tablette Marcoumar mit Wasser", T0.replace(hour=13, minute=45),
                          "Spitex", kind="medikament", now=clock.wall)
    assert [r["stage"] for r in appts.list_reminders()] == ["main"]
    clock.advance(minutes=45)
    sched.tick()
    assert sched.on_hook_off() == "Guten Tag. Eine Erinnerung an Ihre Medikamente: 1 Tablette Marcoumar mit Wasser."


def test_waits_while_call_is_running(setup):
    appts, clock, ringer, sched, state = setup
    appts.add_appointment("Coiffeur", T0.replace(hour=13, minute=5), "Senior",
                          pre_minutes=0, now=clock.wall)
    state["in_call"] = True
    clock.advance(minutes=5)
    sched.tick()
    assert not ringer.ringing
    state["in_call"] = False                 # hung up
    sched.tick()
    assert ringer.ringing


def test_stale_reminder_is_not_rung_hours_late(setup):
    appts, clock, ringer, sched, _ = setup
    appts.add_appointment("Turnen", T0.replace(hour=13, minute=5), "Senior",
                          pre_minutes=0, now=clock.wall)
    clock.advance(hours=3)                   # device was off
    sched.tick()
    assert not ringer.ringing and _status(appts)["status"] == "verpasst"


def test_created_by_is_stored(setup):
    appts, clock, *_ = setup
    appts.add_appointment("Arzt", T0.replace(hour=15), "Spitex Frau Huber", now=clock.wall)
    assert {r["created_by"] for r in appts.list_reminders()} == {"Spitex Frau Huber"}


def test_deleted_7_days_after_appointment(env, setup):
    appts, clock, *_ = setup
    appts.add_appointment("Zahnarzt GeheimTermin42", T0.replace(hour=15), "Spitex", now=clock.wall)
    assert appts.purge_expired(clock.wall + timedelta(days=6)) == 0
    assert appts.purge_expired(clock.wall + timedelta(days=7, hours=3)) == 1
    assert appts.list_reminders() == []
    assert env.files_containing("GeheimTermin42") == []


def test_invalid_input_rejected(setup):
    appts, clock, *_ = setup
    with pytest.raises(ValueError):
        appts.add_appointment("x", T0, "Spitex", kind="party", now=clock.wall)
    with pytest.raises(ValueError):
        appts.add_appointment("x", T0, "  ", now=clock.wall)


def test_core_announces_reminder_then_starts_conversation(env, monkeypatch):
    core_mod = env.load("core_service")
    hw = __import__("hardware")
    appts = __import__("appointments")
    sent, said = [], []

    class FakeSupervisor:
        on_restart = None

        def send(self, kind, **kw):
            sent.append(kind)

        def check(self):
            pass

    ringer = FakeRinger()
    core = core_mod.Core(FakeSupervisor(), ringer, announce=said.append)
    now = datetime.now(timezone.utc)
    appts.add_appointment("Arzt", (now + timedelta(seconds=1)).astimezone(ZH), "Spitex",
                          pre_minutes=0, now=now - timedelta(minutes=1))
    import time
    time.sleep(1.1)
    core.tick()
    assert ringer.ringing
    core.handle(hw.InputEvent("hook_off"))
    for _ in range(50):
        if sent:
            break
        time.sleep(0.02)
    assert said and said[0].startswith("Guten Tag. Eine Erinnerung")
    assert sent == ["call_start"]
