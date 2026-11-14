"""Decision A12: Help and the core keep working when the dialog/LLM hangs."""

import os
import sys
import time
from pathlib import Path

import pytest

HELPER = Path(__file__).parent / "helpers" / "fake_dialog.py"
PIPELINE = Path(__file__).parent.parent / "pipeline"


@pytest.fixture
def core_mod(env, monkeypatch):
    core = env.load("core_service")
    monkeypatch.setattr(core, "PING_INTERVAL", 0.1)
    monkeypatch.setattr(core, "HEARTBEAT_TIMEOUT", 1.0)
    monkeypatch.setattr(core, "LLM_HANG_TIMEOUT", 1.0)
    monkeypatch.setenv("PIPELINE_DIR", str(PIPELINE))
    return core


def _make_core(core_mod, monkeypatch, mode, tmp_path):
    monkeypatch.setenv("FAKE_DIALOG_MODE", mode)
    monkeypatch.setenv("FAKE_DIALOG_LOG", str(tmp_path / "dialog.log"))
    helps, announcements = [], []

    class Help(core_mod.HelpHandler):
        def trigger(self):
            helps.append(time.monotonic())

    hw = __import__("hardware")
    sup = core_mod.DialogSupervisor(command=[sys.executable, str(HELPER)])
    core = core_mod.Core(sup, hw.SimulatedRinger(), help_handler=Help(),
                         announce=announcements.append)
    sup.start()
    return core, sup, helps, announcements


def _run_ticks(core, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        core.tick()
        time.sleep(0.05)


def test_healthy_dialog_is_not_restarted(core_mod, monkeypatch, tmp_path):
    core, sup, _, _ = _make_core(core_mod, monkeypatch, "normal", tmp_path)
    try:
        _run_ticks(core, 2.0)
        assert sup.restarts == 0
    finally:
        sup.stop()


def test_stuck_dialog_is_restarted(core_mod, monkeypatch, tmp_path):
    core, sup, _, _ = _make_core(core_mod, monkeypatch, "silent", tmp_path)
    try:
        _run_ticks(core, 2.5)
        assert sup.restarts >= 1
    finally:
        sup.stop()


def test_llm_hang_restarts_and_announces_during_call(core_mod, monkeypatch, tmp_path):
    hw = __import__("hardware")
    core, sup, _, announcements = _make_core(core_mod, monkeypatch, "llm_hang", tmp_path)
    try:
        core.handle(hw.InputEvent("hook_off"))
        _run_ticks(core, 2.5)
        assert sup.restarts >= 1
        assert announcements and announcements[0] == core_mod.HANG_MESSAGE
    finally:
        sup.stop()


def test_crashing_dialog_is_restarted_with_backoff(core_mod, monkeypatch, tmp_path):
    core, sup, _, _ = _make_core(core_mod, monkeypatch, "crash", tmp_path)
    try:
        _run_ticks(core, 2.0)
        assert 1 <= sup.restarts <= 3   # backoff 1 s, 2 s, ...: no tight loop
    finally:
        sup.stop()


def test_help_works_while_dialog_hangs(core_mod, monkeypatch, tmp_path):
    hw = __import__("hardware")
    core, sup, helps, _ = _make_core(core_mod, monkeypatch, "silent", tmp_path)
    try:
        core.handle(hw.InputEvent("hook_off"))
        t0 = time.monotonic()
        core.handle(hw.InputEvent("button", "hilfe"))
        assert len(helps) == 1 and helps[0] - t0 < 0.1   # immediate, no dialog involved
    finally:
        sup.stop()


def test_hook_and_buttons_go_to_dialog(core_mod, monkeypatch, tmp_path):
    hw = __import__("hardware")
    core, sup, _, _ = _make_core(core_mod, monkeypatch, "normal", tmp_path)
    try:
        core.handle(hw.InputEvent("hook_off"))
        core.handle(hw.InputEvent("button", "heute"))
        core.handle(hw.InputEvent("hook_on"))
        time.sleep(0.3)
        log = (tmp_path / "dialog.log").read_text().split()
        assert [m for m in log if m != "ping"] == ["call_start", "button", "call_end"]
        assert core.in_call is False
    finally:
        sup.stop()


@pytest.mark.parametrize("line,kind,name", [
    ("a", "hook_off", ""), ("h", "hook_on", ""), ("hilfe", "button", "hilfe"),
    ("Kalender", "button", "kalender"), ("q", "quit", ""),
])
def test_keyboard_commands(env, line, kind, name):
    hw = env.load("hardware")
    event = hw.parse_command(line)
    assert (event.kind, event.name) == (kind, name)


class _Sup:
    """Supervisor stand-in: the dialog is absent until ready() is called."""
    def __init__(self):
        self.sent, self.up = [], False
        self.on_restart = self.on_ready = None

    def send(self, kind, **kw):
        if not self.up:
            return False
        self.sent.append(kind)
        return True

    def check(self):
        pass


def test_handset_lifted_during_restart_starts_call_when_ready(env):
    core_mod = env.load("core_service")
    hw = __import__("hardware")
    sup = _Sup()
    core = core_mod.Core(sup, hw.SimulatedRinger(), with_reminders=False)
    core.handle(hw.InputEvent("hook_off"))  # dialog in restart backoff
    assert sup.sent == []
    sup.up = True
    core._on_dialog_ready()
    assert sup.sent == ["call_start"]
    core._on_dialog_ready()                  # no duplicate
    assert sup.sent == ["call_start"]


def test_hung_up_before_ready_starts_nothing(env):
    core_mod = env.load("core_service")
    hw = __import__("hardware")
    sup = _Sup()
    core = core_mod.Core(sup, hw.SimulatedRinger(), with_reminders=False)
    core.handle(hw.InputEvent("hook_off"))
    core.handle(hw.InputEvent("hook_on"))
    sup.up = True
    core._on_dialog_ready()
    assert sup.sent == []


def test_hang_announcement_does_not_block_core(env):
    core_mod = env.load("core_service")
    hw = __import__("hardware")
    said = []

    def slow_announce(text):
        time.sleep(1.0)
        said.append(text)
    core = core_mod.Core(_Sup(), hw.SimulatedRinger(), announce=slow_announce,
                         with_reminders=False)
    core.in_call = True
    t = time.monotonic()
    core._on_dialog_restart("LLM hang")
    assert time.monotonic() - t < 0.2
    time.sleep(1.2)
    assert said == [core_mod.HANG_MESSAGE]
