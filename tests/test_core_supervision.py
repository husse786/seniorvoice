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
