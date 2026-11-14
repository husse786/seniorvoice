#!/usr/bin/env python3
"""Core process of the SeniorVoice telephone (decision A12).

The core is always on and contains no language-model code. It
- reads the hook switch and the buttons,
- handles Help itself (A3, A13, A14; full Help flow in PR 6),
- runs scheduled tasks (reminders, callback, purge; PR 4/5),
- starts the dialog process (speech recognition, LLM, speech output) as a
  child and supervises it: if the dialog crashes, stops answering, or the
  LLM hangs, the core kills and restarts it.

So Help and reminders keep working when the LLM hangs (condition of A12).
"""

import argparse
import itertools
import os
import queue
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable

from logging_config import setup_logging, get_logger
from bus import Bus, BUS_FD_ENV
from hardware import (AudioRinger, GpioInput, InputEvent, KeyboardInput, Ringer,
                      SimulatedRinger)

log = get_logger("core")

DIALOG_SCRIPT = Path(__file__).with_name("dialog_service.py")

PING_INTERVAL = float(os.getenv("CORE_PING_INTERVAL", "5"))
# No pong for this long: dialog process is stuck (not just a slow LLM)
HEARTBEAT_TIMEOUT = float(os.getenv("CORE_HEARTBEAT_TIMEOUT", "20"))
# The dialog reports "thinking" while waiting for the LLM. Longer than this
# counts as an LLM hang (LLM_TIMEOUT is 60 s by default; this is a backstop).
LLM_HANG_TIMEOUT = float(os.getenv("CORE_LLM_HANG_TIMEOUT", "90"))
RESTART_BACKOFF_MAX = 60.0

# Buttons whose answer is spoken in the handset (A9): lift it first
HANDSET_BUTTONS = ("familie", "heute", "kalender")
LIFT_HANDSET = "Bitte heben Sie zuerst den Hörer ab und drücken Sie dann den Knopf nochmals."

HANG_MESSAGE = (
    "Entschuldigung, ich habe gerade ein technisches Problem. "
    "Bitte legen Sie kurz auf und heben Sie dann wieder ab."
)


class DialogSupervisor:
    """Starts the dialog process and restarts it when it fails or hangs."""

    def __init__(self, command: list[str] | None = None,
                 on_restart: Callable[[str], None] | None = None,
                 clock: Callable[[], float] = time.monotonic):
        self.command = command or [sys.executable, str(DIALOG_SCRIPT)]
        self.on_restart = on_restart or (lambda reason: None)
        self.on_ready: Callable[[], None] = lambda: None
        self.clock = clock
        self.proc: subprocess.Popen | None = None
        self.bus: Bus | None = None
        self.state = "starting"
        self.state_since = clock()
        self.last_pong = clock()
        self.last_ping = 0.0
        self.restarts = 0
        self._backoff = 1.0
        self._next_start = 0.0
        self._lock = threading.Lock()

    # --- lifecycle ---

    def start(self) -> None:
        parent_sock, child_sock = socket.socketpair()
        env = dict(os.environ, **{BUS_FD_ENV: str(child_sock.fileno())})
        self.proc = subprocess.Popen(
            self.command, pass_fds=[child_sock.fileno()], env=env,
        )
        child_sock.close()
        self.bus = Bus(parent_sock)
        now = self.clock()
        with self._lock:
            self.state = "starting"
            self.state_since = now
            self.last_pong = now
        self.bus.listen(self._on_message, name="dialog-bus")
        log.info("Dialog process started (pid %d)", self.proc.pid)

    def stop(self) -> None:
        if self.bus:
            self.bus.close()
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()

    def _restart(self, reason: str) -> None:
        log.warning("Restarting dialog process: %s", reason)
        self.restarts += 1
        if self.proc and self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait()
        if self.bus:
            self.bus.close()
        self.proc = None
        self._next_start = self.clock() + self._backoff
        self._backoff = min(self._backoff * 2, RESTART_BACKOFF_MAX)
        self.on_restart(reason)

    # --- messages ---

    def _on_message(self, msg: dict) -> None:
        kind = msg.get("type")
        now = self.clock()
        with self._lock:
            if kind == "pong":
                self.last_pong = now
            elif kind == "state":
                self.state = msg.get("state", "unknown")
                self.state_since = now
                self.last_pong = now
                if self.state == "ready":
                    self._backoff = 1.0
        if kind == "state" and msg.get("state") == "ready":
            self.on_ready()

    def send(self, msg_type: str, **fields) -> bool:
        if self.bus is None or self.proc is None:
            return False
        return self.bus.send(msg_type, **fields)

    # --- watchdog, called regularly by the core loop ---

    def check(self) -> None:
        now = self.clock()
        if self.proc is None:
            if now >= self._next_start:
                self.start()
            return
        if self.proc.poll() is not None:
            self._restart(f"exited with code {self.proc.returncode}")
            return
        with self._lock:
            state, since, last_pong = self.state, self.state_since, self.last_pong
        if state == "thinking" and now - since > LLM_HANG_TIMEOUT:
            self._restart(f"LLM hang (thinking for {now - since:.0f}s)")
            return
        if now - last_pong > HEARTBEAT_TIMEOUT:
            self._restart(f"no heartbeat for {now - last_pong:.0f}s")
            return
        if now - self.last_ping >= PING_INTERVAL:
            self.last_ping = now
            self.send("ping")


class HelpHandler:
    """Interface of the Help button handler (help_alert.HelpService)."""

    def trigger(self) -> None:
        log.warning("HELP pressed (no handler configured)")


class Core:
    """State machine of the telephone. No LLM code in here."""

    def __init__(self, supervisor: DialogSupervisor, ringer: Ringer,
                 help_handler: HelpHandler | None = None,
                 announce: Callable[[str], None] | None = None,
                 with_reminders: bool = True,
                 announce_handset: Callable[[str], None] | None = None):
        self.supervisor = supervisor
        self.ringer = ringer
        self.help = help_handler or HelpHandler()
        # Room speaker: Help, "please lift the handset" (A13). Handset: what the
        # person on the phone hears, e.g. the reminder after pickup (A9)
        self.announce = announce or (lambda text: None)
        self.announce_handset = announce_handset or self.announce
        self.events: "queue.Queue[InputEvent]" = queue.Queue()
        self.in_call = False
        # call_start reached the current dialog process (False after a restart)
        self.call_delivered = False
        self.announcing = False
        self._call_lock = threading.Lock()
        self.tickers: list[Callable[[], None]] = [supervisor.check]
        self.running = True
        self.failed = False
        supervisor.on_restart = self._on_dialog_restart
        supervisor.on_ready = self._on_dialog_ready
        self.reminders = None
        if with_reminders:
            from appointments import ReminderScheduler
            self.reminders = ReminderScheduler(ringer, in_call=lambda: self.in_call)
            self.tickers.append(self.reminders.tick)

    def _say(self, text: str, output: str = "speaker") -> bool:
        """Play a fixed sentence (no LLM). False if it could not be played."""
        speak = self.announce_handset if output == "handset" else self.announce
        try:
            return speak(text) is not False
        except Exception as e:
            log.error("Announcement failed: %s", type(e).__name__)
            return False

    def _say_async(self, text: str, output: str = "speaker") -> None:
        """Never block the core loop (Help, hook, reminders) with audio."""
        threading.Thread(target=self._say, args=(text, output), daemon=True).start()

    def _on_dialog_restart(self, reason: str) -> None:
        with self._call_lock:
            self.call_delivered = False
        if self.in_call:
            self._say_async(HANG_MESSAGE, output="handset")

    def _on_dialog_ready(self) -> None:
        # Handset lifted while the dialog was (re)starting: start the call now
        self._start_call_if_pending()

    def _start_call_if_pending(self) -> None:
        with self._call_lock:
            if self.in_call and not self.announcing and not self.call_delivered:
                self.call_delivered = self.supervisor.send("call_start")

    def handle(self, event: InputEvent) -> None:
        if event.kind == "quit":
            self.running = False
        elif event.kind == "input_failed":
            log.critical("Input hardware failed, core exits for a restart")
            self.failed = True
            self.running = False
        elif event.kind == "hook_off":
            self.in_call = True
            text = self.reminders.on_hook_off() if self.reminders else None
            self.ringer.stop()
            if text:
                # Reminder first (fixed text, no LLM), then normal conversation
                self.announcing = True

                def announce_then_talk():
                    ok = self._say(text, output="handset")
                    self.reminders.announced(ok)
                    self.announcing = False
                    self._start_call_if_pending()
                threading.Thread(target=announce_then_talk, daemon=True).start()
            else:
                self._start_call_if_pending()
        elif event.kind == "hook_on":
            self.in_call = False
            with self._call_lock:
                self.call_delivered = False
            self.supervisor.send("call_end")
        elif event.kind == "sim_ack" and hasattr(self.help, "simulate_ack"):
            self.help.simulate_ack()
        elif event.kind == "button" and event.name == "hilfe":
            # Never through the dialog process: works even if it hangs
            self.help.trigger()
        elif event.kind == "button" and event.name in HANDSET_BUTTONS and not self.in_call:
            self._say_async(LIFT_HANDSET)
        elif event.kind == "button":
            self.supervisor.send("button", name=event.name)

    def tick(self) -> None:
        for ticker in self.tickers:
            try:
                ticker()
            except Exception as e:
                log.error("Ticker %s failed: %s", getattr(ticker, "__name__", ticker), e)

    def run(self, tick_interval: float = 1.0) -> None:
        self.supervisor.start()
        try:
            while self.running:
                try:
                    event = self.events.get(timeout=tick_interval)
                    self.handle(event)
                except queue.Empty:
                    pass
                self.tick()
        finally:
            self.supervisor.stop()


class AnnouncementQueue:
    """All fixed sentences of the core, one after another on one thread.

    Help sentences (urgent) go before waiting reminder or restart sentences,
    so they never overlap other core speech. Help and "please lift the
    handset" use the room speaker (A13); sentences for the person on the
    phone (reminder after pickup, restart notice) use the handset (A9).
    """

    def __init__(self, speak: Callable[..., None], ringer=None):
        self._speak = speak
        self._ringer = ringer          # paused while speaking: same speaker device
        self._queue: "queue.PriorityQueue" = queue.PriorityQueue()
        self._seq = itertools.count()
        threading.Thread(target=self._run, name="announce", daemon=True).start()

    def say(self, text: str, urgent: bool = False, output: str = "speaker") -> None:
        self._queue.put((0 if urgent else 1, next(self._seq), text, output, None))

    def say_urgent(self, text: str) -> None:
        self.say(text, urgent=True)

    def say_and_wait(self, text: str, output: str = "speaker") -> bool:
        """Play and wait; False if it could not be played."""
        done = {"event": threading.Event(), "ok": False}
        self._queue.put((1, next(self._seq), text, output, done))
        done["event"].wait()
        return done["ok"]

    def _run(self) -> None:
        while True:
            _prio, _seq, text, output, done = self._queue.get()
            ok = False
            # The ring uses the room speaker: free it only for speaker sentences
            pause = getattr(self._ringer, "pause", None) if output == "speaker" else None
            try:
                if pause:
                    pause()
                if output == "speaker":
                    self._speak(text)
                else:
                    self._speak(text, output=output)
                ok = True
            except Exception as e:
                log.error("Announcement failed: %s", type(e).__name__)
            finally:
                if pause:
                    self._ringer.resume()
            if done is not None:
                done["ok"] = ok
                done["event"].set()


def _speak(text: str, output: str = "speaker") -> None:
    """Announcement from the core (no LLM). Raises if it cannot be played."""
    from tts import speak
    speak(text, output=output)


def main() -> None:
    parser = argparse.ArgumentParser(description="SeniorVoice core process")
    parser.add_argument("--input", choices=["keyboard", "gpio"], default="keyboard",
                        help="keyboard simulation or the telephone on the Pi (GPIO)")
    args = parser.parse_args()

    setup_logging()
    from privacy_migration import run_legacy_purge
    try:
        run_legacy_purge()
    except Exception as e:
        log.critical("Legacy purge failed, not starting: %s", e)
        sys.exit(1)

    from config import MEMORY_PURGE_INTERVAL
    from memory import PurgeService
    PurgeService(interval=MEMORY_PURGE_INTERVAL).start()

    from channels import channel_from_env
    from help_alert import HelpService
    # Help speaks through a queue: the core loop never waits for audio
    ringer = AudioRinger() if args.input == "gpio" else SimulatedRinger()
    voice = AnnouncementQueue(_speak, ringer=ringer)
    help_service = HelpService(channel_from_env(), announce=voice.say_urgent,
                               senior_name=os.getenv("SENIOR_NAME", ""))
    help_service.run_worker()
    from family import run_sender
    run_sender(help_service.channel)
    core = Core(DialogSupervisor(), ringer, help_handler=help_service,
                announce=voice.say_and_wait,
                announce_handset=lambda text: voice.say_and_wait(text, output="handset"))
    if args.input == "gpio":
        GpioInput().start(core.events)
    else:
        KeyboardInput().start(core.events)
    signal.signal(signal.SIGTERM, lambda *a: setattr(core, "running", False))
    log.info("Core started")
    core.run()
    log.info("Core stopped")
    if core.failed:
        sys.exit(1)   # systemd restarts the service


if __name__ == "__main__":
    main()
