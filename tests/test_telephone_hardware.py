"""PR 7: hook switch and buttons over GPIO, ringer, audio routing, Heute/Kalender."""

import queue
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

ZH = ZoneInfo("Europe/Zurich")


class FakeLgpio:
    SET_PULL_UP = 32

    def __init__(self, levels):
        self.levels = dict(levels)
        self.claimed = []

    def gpiochip_open(self, chip):
        self.chip = chip
        return 7

    def gpio_claim_input(self, handle, pin, flags):
        self.claimed.append((pin, flags))

    def gpio_read(self, handle, pin):
        return self.levels[pin]

    def gpiochip_close(self, handle):
        pass


PINS = {5: "sprechen", 6: "heute", 13: "kalender", 19: "rat", 26: "familie", 21: "hilfe"}


def _gpio(env, levels=None):
    hw = env.load("hardware")
    levels = levels or {17: 0, **{p: 1 for p in PINS}}     # on hook, nothing pressed
    lg = FakeLgpio(levels)
    clock = {"t": 0.0}
    gi = hw.GpioInput(lgpio_module=lg, chip=4, hook_pin=17, offhook_level=1,
                      button_pins=dict(PINS), debounce_ms=30,
                      monotonic=lambda: clock["t"])
    handle = gi._open()
    stable = {p: lg.gpio_read(handle, p) for p in [17, *PINS]}
    return hw, gi, lg, clock, handle, stable


def _rounds(gi, handle, stable, clock, events, ms):
    pending = gi.__dict__.setdefault("_test_pending", {})
    for _ in range(ms // 10):
        gi.poll(handle, stable, pending, events)
        clock["t"] += 0.01


def test_pull_ups_on_all_pins(env):
    hw, gi, lg, *_ = _gpio(env)
    assert sorted(p for p, _ in lg.claimed) == sorted([17, *PINS])
    assert {f for _, f in lg.claimed} == {FakeLgpio.SET_PULL_UP}


def test_lift_and_hang_up_after_debounce(env):
    hw, gi, lg, clock, handle, stable = _gpio(env)
    events = queue.Queue()
    lg.levels[17] = 1                                     # lifted
    _rounds(gi, handle, stable, clock, events, 20)
    assert events.empty()                                 # not before 30 ms
    _rounds(gi, handle, stable, clock, events, 30)
    assert events.get_nowait() == hw.InputEvent("hook_off")
    lg.levels[17] = 0
    _rounds(gi, handle, stable, clock, events, 60)
    assert events.get_nowait() == hw.InputEvent("hook_on")
    assert events.empty()


def test_bounce_produces_no_event(env):
    hw, gi, lg, clock, handle, stable = _gpio(env)
    events = queue.Queue()
    pending = {}
    for i in range(10):                                   # contact bounce, 10 ms each
        lg.levels[17] = i % 2
        gi.poll(handle, stable, pending, events)
        clock["t"] += 0.01
    lg.levels[17] = 0
    _rounds(gi, handle, stable, clock, events, 60)
    assert events.empty()


def test_button_press_once_on_press_not_release(env):
    hw, gi, lg, clock, handle, stable = _gpio(env)
    events = queue.Queue()
    lg.levels[21] = 0                                     # Hilfe pressed
    _rounds(gi, handle, stable, clock, events, 60)
    assert events.get_nowait() == hw.InputEvent("button", "hilfe")
    lg.levels[21] = 1                                     # released
    _rounds(gi, handle, stable, clock, events, 60)
    assert events.empty()


def test_handset_already_lifted_at_start(env):
    hw = env.load("hardware")
    lg = FakeLgpio({17: 1, **{p: 1 for p in PINS}})
    gi = hw.GpioInput(lgpio_module=lg, chip=4, hook_pin=17, offhook_level=1,
                      button_pins=dict(PINS), sleep=lambda s: time.sleep(0.01))
    events = queue.Queue()
    gi.start(events)
    assert events.empty()                                 # not at once (debounce)
    try:
        assert events.get(timeout=1) == hw.InputEvent("hook_off")
    finally:
        gi.running = False


def test_glitch_at_start_starts_no_call(env):
    hw, gi, lg, clock, handle, stable = _gpio(env)
    stable[17] = 0                                        # as start() sets it
    events = queue.Queue()
    lg.levels[17] = 1
    _rounds(gi, handle, stable, clock, events, 10)        # 10 ms glitch
    lg.levels[17] = 0
    _rounds(gi, handle, stable, clock, events, 60)
    assert events.empty()


def test_unreadable_gpio_makes_core_exit(env):
    hw = env.load("hardware")

    class Broken(FakeLgpio):
        reads = 0

        def gpio_read(self, handle, pin):
            Broken.reads += 1
            if Broken.reads > 7:                          # after the start reads
                raise OSError("gpio gone")
            return 1
    gi = hw.GpioInput(lgpio_module=Broken({}), chip=4, hook_pin=17, offhook_level=1,
                      button_pins=dict(PINS), sleep=lambda s: None)
    events = queue.Queue()
    gi.start(events)
    assert events.get(timeout=2) == hw.InputEvent("input_failed")
    core_mod = env.load("core_service")
    hw2 = __import__("hardware")

    class Sup:
        on_restart = None

        def send(self, *a, **k):
            return True

        def check(self):
            pass
    core = core_mod.Core(Sup(), hw2.SimulatedRinger(), with_reminders=False)
    core.handle(hw2.InputEvent("input_failed"))
    assert core.failed and not core.running


def test_configured_device_never_falls_back_to_default(env, monkeypatch):
    monkeypatch.setenv("HANDSET_ALSA_DEVICE", "plughw:CARD=Device,DEV=0")
    tts = env.load("tts")
    monkeypatch.setattr(tts.shutil, "which", lambda name: "/usr/bin/paplay" if name == "paplay" else None)
    from pathlib import Path
    with pytest.raises(RuntimeError):
        tts.player_command(Path("a.wav"))


def test_announcement_pauses_ringing(env):
    core_mod = env.load("core_service")
    hw = __import__("hardware")
    ringer = hw.AudioRinger(command=lambda: [sys.executable, "-c", "import time; time.sleep(30)"])
    ringer.ring()
    time.sleep(0.3)
    seen = []

    def speak(text):
        proc = ringer._proc
        seen.append(proc is None or proc.poll() is not None)   # ring player has ended
    q = core_mod.AnnouncementQueue(speak, ringer=ringer)
    assert q.say_and_wait("Hilfe") is True
    assert seen == [True]
    time.sleep(0.3)
    assert ringer.ringing and ringer._proc.poll() is None       # ringing resumed
    ringer.stop()


def test_button_pin_config_is_checked(env):
    hw = env.load("hardware")
    assert hw.parse_button_pins("sprechen:5,heute:6,kalender:13,rat:19,familie:26,hilfe:21") == PINS
    with pytest.raises(ValueError):
        hw.parse_button_pins("sprechen:5,heute:5,kalender:13,rat:19,familie:26,hilfe:21")
    with pytest.raises(ValueError):
        hw.parse_button_pins("sprechen:5")                # buttons missing
    with pytest.raises(ValueError):
        hw.GpioInput(lgpio_module=FakeLgpio({}), hook_pin=5, button_pins=dict(PINS))


def test_ringer_stops_mid_ring(env):
    hw = env.load("hardware")
    ringer = hw.AudioRinger(command=lambda: [sys.executable, "-c", "import time; time.sleep(30)"])
    ringer.ring()
    time.sleep(0.3)
    assert ringer.ringing
    t = time.monotonic()
    ringer.stop()
    ringer._thread.join(2)
    assert not ringer.ringing and time.monotonic() - t < 2


def test_handset_and_speaker_use_separate_devices(env, monkeypatch):
    monkeypatch.setenv("HANDSET_ALSA_DEVICE", "plughw:CARD=Device,DEV=0")
    monkeypatch.setenv("SPEAKER_ALSA_DEVICE", "plughw:CARD=Headphones,DEV=0")
    tts = env.load("tts")
    monkeypatch.setattr(tts.shutil, "which", lambda name: f"/usr/bin/{name}")
    from pathlib import Path
    assert tts.player_command(Path("a.wav"))[3] == "plughw:CARD=Device,DEV=0"
    assert tts.player_command(Path("a.wav"), "speaker")[3] == "plughw:CARD=Headphones,DEV=0"


def test_today_text(env):
    appts = env.load("appointments")
    now = datetime(2026, 11, 20, 7, 0, tzinfo=ZH)
    appts.add_appointment("Arzttermin bei Dr. Meier", now.replace(hour=14), "Spitex", now=now)
    appts.add_appointment("1 Tablette Marcoumar", now.replace(hour=8), "Spitex",
                          kind="medikament", now=now)
    appts.add_appointment("Coiffeur", now + timedelta(days=1), "Senior", now=now)
    assert appts.today_text(now) == (
        "Heute ist Freitag, der 20. November. Heute haben Sie um 14 Uhr Arzttermin bei Dr. Meier. "
        "Ihre Medikamente: um 8 Uhr: 1 Tablette Marcoumar.")


def test_week_text_without_medication(env):
    appts = env.load("appointments")
    now = datetime(2026, 11, 20, 7, 0, tzinfo=ZH)
    appts.add_appointment("Coiffeur", now.replace(hour=10, minute=30) + timedelta(days=1), "Senior", now=now)
    appts.add_appointment("Podologie", now.replace(hour=9) + timedelta(days=3), "Tochter", now=now)
    appts.add_appointment("Tablette", now.replace(hour=8) + timedelta(days=1), "Spitex",
                          kind="medikament", now=now)
    appts.add_appointment("Zu spät", now + timedelta(days=8), "Senior", now=now)
    assert appts.week_text(now) == (
        "In den nächsten sieben Tagen haben Sie: morgen um 10:30 Uhr Coiffeur; "
        "am Montag, der 23. November um 9 Uhr Podologie.")
    assert "keine Termine" in appts.week_text(now + timedelta(days=30))


def test_heute_button_in_call_reads_without_llm(env, monkeypatch):
    import socket, types
    from conftest import patch_http
    env.load("main")
    dialog = __import__("dialog_service")
    bus_mod = __import__("bus")
    a, b = socket.socketpair()
    service = dialog.DialogService(bus_mod.Bus(b))
    spoken, calls = [], []
    for name, attrs in {
        "audio_capture": {"record_until_silence": lambda: b"RIFF"},
        "stt": {"transcribe": lambda wav: ""},
        "tts": {"speak": lambda text, output="handset": (spoken.append(text),
                                                         service.call_active.clear())},
    }.items():
        mod = types.ModuleType(name)
        for k, v in attrs.items():
            setattr(mod, k, v)
        monkeypatch.setitem(sys.modules, name, mod)
    import llm_backend
    patch_http(llm_backend, monkeypatch, lambda req, timeout=None: calls.append(1))
    service.on_message({"type": "call_start"})
    service.on_message({"type": "button", "name": "heute"})
    service.run_call()
    assert spoken and spoken[0].startswith("Heute ist") and calls == []


def test_unhandled_buttons_do_not_end_the_turn(env):
    import socket
    env.load("main")
    dialog = __import__("dialog_service")
    bus_mod = __import__("bus")
    a, b = socket.socketpair()
    service = dialog.DialogService(bus_mod.Bus(b))
    service.on_message({"type": "button", "name": "sprechen"})
    assert service.pending_button is None


def test_kalender_without_handset_asks_to_lift(env):
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
    core.handle(hw.InputEvent("button", "kalender"))
    for _ in range(50):
        if said:
            break
        time.sleep(0.01)
    assert said == [core_mod.LIFT_HANDSET] and sent == []


def test_core_sentences_for_the_caller_go_to_the_handset(env):
    """A9/A13: reminder after pickup and restart notice in the handset;
    "please lift the handset" on the room speaker."""
    core_mod = env.load("core_service")
    hw = __import__("hardware")
    appts = __import__("appointments")
    speaker, handset, sent = [], [], []

    class Sup:
        on_restart = None

        def send(self, kind, **kw):
            sent.append(kind)
            return True

        def check(self):
            pass
    core = core_mod.Core(Sup(), hw.SimulatedRinger(), announce=speaker.append,
                         announce_handset=handset.append)
    now = datetime.now(timezone.utc)
    appts.add_appointment("Arzt", (now + timedelta(seconds=1)).astimezone(ZoneInfo("Europe/Zurich")),
                          "Spitex", pre_minutes=0, now=now - timedelta(minutes=1))
    time.sleep(1.1)
    core.tick()
    core.handle(hw.InputEvent("hook_off"))
    for _ in range(100):
        if sent:
            break
        time.sleep(0.02)
    assert handset and handset[0].startswith("Guten Tag. Eine Erinnerung")
    core._on_dialog_restart("test")
    for _ in range(50):
        if len(handset) == 2:
            break
        time.sleep(0.01)
    assert handset[1] == core_mod.HANG_MESSAGE
    core.handle(hw.InputEvent("hook_on"))
    core.handle(hw.InputEvent("button", "heute"))
    for _ in range(50):
        if speaker:
            break
        time.sleep(0.01)
    assert speaker == [core_mod.LIFT_HANDSET] and len(handset) == 2


def test_announcement_queue_routes_output_and_pauses_ring_only_for_speaker(env):
    core_mod = env.load("core_service")
    played, events = [], []

    class Ringer:
        def pause(self):
            events.append("pause")

        def resume(self):
            events.append("resume")

    def speak(text, output="speaker"):
        played.append((text, output))
    q = core_mod.AnnouncementQueue(speak, ringer=Ringer())
    assert q.say_and_wait("Erinnerung", output="handset") is True
    assert events == []
    assert q.say_and_wait("Hilfe") is True
    assert played == [("Erinnerung", "handset"), ("Hilfe", "speaker")]
    assert events == ["pause", "resume"]
