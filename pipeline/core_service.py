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
import json
import os
import shutil
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
HANDSET_BUTTONS = ("sprechen", "familie", "heute", "kalender", "rat")
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
        # Text mode of the simulation: sentences of the dialog for the phone page
        self.on_sim_say: Callable[[str, str], None] = lambda text, output: None
        self.on_sim_heard: Callable[[str], None] = lambda text: None
        self.last_restart = ""          # "exited", "llm_hang" or "no_heartbeat"
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
        self.last_restart = ("llm_hang" if reason.startswith("LLM hang") else
                             "no_heartbeat" if reason.startswith("no heartbeat") else "exited")
        try:
            import metrics
            metrics.log_event("dialog_hang" if self.last_restart == "llm_hang" else "dialog_restart")
        except Exception as e:
            log.error("Metrics event failed: %s", type(e).__name__)
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
        elif kind == "sim_say" and isinstance(msg.get("text"), str):
            self.on_sim_say(msg["text"], str(msg.get("output", "handset")))
        elif kind == "sim_heard" and isinstance(msg.get("text"), str):
            self.on_sim_heard(msg["text"])

    def health_state(self) -> str:
        """Dialog state for the health view. Deliberately coarse: whether a
        conversation is going on right now is not shown (daily routine)."""
        with self._lock:
            state = self.state
        if self.proc is None:
            return "neustart"
        if state in ("starting", "loading"):
            return "laedt"
        if state in ("ready", "idle", "listening", "thinking", "speaking"):
            return "bereit"
        return "unbekannt"

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
        self.opened_with = ""        # reminder spoken at pickup (RAM only)
        self.screen = None           # screen.Screen when a display is used
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
            # Handset is busy with the notice: the restarted dialog starts the
            # call only after it (like the reminder after pickup)
            self.announcing = True

            def notice():
                self._say(HANG_MESSAGE, output="handset")
                self.announcing = False
                self._start_call_if_pending()
            threading.Thread(target=notice, daemon=True).start()

    def _on_dialog_ready(self) -> None:
        # Handset lifted while the dialog was (re)starting: start the call now
        self._start_call_if_pending()

    def _start_call_if_pending(self) -> None:
        with self._call_lock:
            if self.in_call and not self.announcing and not self.call_delivered:
                # opened_with: the reminder just spoken, so the dialog does
                # not greet again and the LLM knows what "Ja, danke" refers to
                self.call_delivered = self.supervisor.send(
                    "call_start", opened_with=self.opened_with)

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
            self.opened_with = text or ""
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
            if self.screen is not None:
                self.screen.forget()          # conversation off the screen (A8)
            with self._call_lock:
                self.call_delivered = False
            self.supervisor.send("call_end")
        elif event.kind == "sim_text":
            # Typed on the simulated phone page: to the dialog (RAM only)
            if self.in_call:
                self.supervisor.send("sim_text", text=event.name)
                if self.screen is not None:
                    self.screen.heard(event.name)
        elif event.kind == "sim_ack" and hasattr(self.help, "simulate_ack"):
            self.help.simulate_ack()
        elif event.kind == "button" and event.name == "hilfe":
            # Never through the dialog process: works even if it hangs
            self.help.trigger()
        elif event.kind == "button" and event.name in HANDSET_BUTTONS and not self.in_call:
            self._say_async(LIFT_HANDSET)
        elif event.kind == "button":
            self.supervisor.send("button", name=event.name)

    def phone_state(self) -> dict:
        """What the simulated phone page shows (this computer only)."""
        is_open = getattr(self.help, "is_open", None)
        return {"in_call": self.in_call, "ringing": bool(getattr(self.ringer, "ringing", False)),
                "announcing": self.announcing, "dialog": self.supervisor.health_state(),
                "help_open": bool(is_open()) if is_open else False}

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


class StatusWriter:
    """Writes the core's technical state for the health view of the device API.

    A small JSON file in RAM (OUTPUT_DIR), rewritten every few seconds; the
    device API treats it as stale (core not running) when it stops changing.
    No content and no sign of whether a call is going on.
    """

    INTERVAL = 5.0

    def __init__(self, core: "Core", input_mode: str, audio_mode: str,
                 channel_name: str, path: Path | None = None,
                 clock: Callable[[], float] = time.monotonic):
        from config import STATUS_FILE
        self.core = core
        self.path = Path(path or STATUS_FILE)
        self.clock = clock
        self.base = {"pid": os.getpid(), "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
                     "input": input_mode, "audio": audio_mode, "channel": channel_name}
        self._last = 0.0

    def __call__(self) -> None:
        now = self.clock()
        if now - self._last < self.INTERVAL:
            return
        self._last = now
        sup = self.core.supervisor
        data = dict(self.base, updated=time.time(), dialog=sup.health_state(),
                    dialog_restarts=sup.restarts, last_restart=sup.last_restart)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        os.replace(tmp, self.path)


class AnnouncementQueue:
    """All fixed sentences of the core, one after another on one thread.

    One queue and thread per output device: Help and "please lift the
    handset" use the room speaker (A13), sentences for the person on the phone
    (reminder after pickup, restart notice) the handset (A9). A handset
    sentence never delays Help. On the speaker, Help (urgent) goes first.
    """

    OUTPUTS = ("speaker", "handset")

    def __init__(self, speak: Callable[..., None], ringer=None):
        self._speak = speak
        self._ringer = ringer          # paused while the speaker talks: same device
        self._seq = itertools.count()
        self._queues: dict[str, "queue.PriorityQueue"] = {}
        for output in self.OUTPUTS:
            self._queues[output] = queue.PriorityQueue()
            threading.Thread(target=self._run, args=(output,),
                             name=f"announce-{output}", daemon=True).start()

    def say(self, text: str, urgent: bool = False, output: str = "speaker") -> None:
        self._queues[output].put((0 if urgent else 1, next(self._seq), text, None))

    def say_urgent(self, text: str) -> None:
        self.say(text, urgent=True)

    def say_and_wait(self, text: str, output: str = "speaker") -> bool:
        """Play and wait; False if it could not be played."""
        done = {"event": threading.Event(), "ok": False}
        self._queues[output].put((1, next(self._seq), text, done))
        done["event"].wait()
        return done["ok"]

    def _run(self, output: str) -> None:
        # The ring uses the room speaker: free it only for speaker sentences
        ringer = self._ringer if output == "speaker" else None
        while True:
            _prio, _seq, text, done = self._queues[output].get()
            ok = False
            try:
                if ringer:
                    ringer.pause()
                self._speak(text, output=output)
                ok = True
            except Exception as e:
                log.error("Announcement failed: %s", type(e).__name__)
            finally:
                if ringer:
                    ringer.resume()
            if done is not None:
                done["ok"] = ok
                done["event"].set()


def _speak(text: str, output: str = "speaker") -> None:
    """Announcement from the core (no LLM). Raises if it cannot be played."""
    from tts import speak
    speak(text, output=output)


def _set_env(name: str, value: str) -> None:
    """For this process (config) and the dialog process it starts (env)."""
    import config
    os.environ[name] = value
    setattr(config, name, value)


def resolve_sim_audio(requested: str) -> tuple[str, str]:
    """Sound or text for the simulation, decided at start without settings.

    Returns (mode, note for the phone page). A configured microphone that is
    not there (e.g. the Pi's C920 on a Mac) falls back to the default one.
    """
    import importlib.util
    import config
    if requested == "text":
        return "text", "Nur Tippen für diesen Start (SIM_AUDIO=text)."
    missing = []
    if shutil.which("piper") is None or not Path(config.PIPER_VOICE).is_file():
        missing.append("Sprachausgabe Piper (Programm oder Stimme)")
    if importlib.util.find_spec("faster_whisper") is None:
        missing.append("Spracherkennung Whisper")
    note = ""
    try:
        import sounddevice as sd
        mics = [d["name"] for d in sd.query_devices() if d["max_input_channels"] > 0]
        wanted = config.AUDIO_DEVICE_NAME.strip()
        if not mics:
            missing.append("Mikrofon")
        else:
            match = [m for m in mics if wanted and wanted.lower() in m.lower()]
            if wanted and not match:
                note = f"«{wanted}» nicht gefunden, Standard-Mikrofon. "
                _set_env("AUDIO_DEVICE_NAME", "")
            used = match[0] if match else _default_mic(sd) or mics[0]
            note = f"Ton an. Mikrofon: {used}. " + note
    except Exception as e:
        missing.append(f"Mikrofon ({type(e).__name__})")
    if missing:
        log.warning("Simulation without sound, missing: %s", ", ".join(missing))
        return "text", "Ton aus, es fehlt: " + ", ".join(missing) + ". Tippen geht."
    return "audio", note + "Tippen geht auch."


def _default_mic(sd) -> str:
    """Name of the system's default microphone (macOS: Systemeinstellungen, Ton)."""
    try:
        return sd.query_devices(kind="input")["name"]
    except Exception:
        return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="SeniorVoice core process")
    parser.add_argument("--input", choices=["web", "keyboard", "gpio"], default=None,
                        help="web = simulated telephone in the browser, keyboard = "
                             "commands on the console, gpio = the telephone on the Pi "
                             "(default: SENIORVOICE_INPUT, else keyboard)")
    args = parser.parse_args()
    if args.input is None:
        import config as _config
        args.input = _config.SENIORVOICE_INPUT
        if args.input not in ("web", "keyboard", "gpio"):
            parser.error("SENIORVOICE_INPUT must be web, keyboard or gpio")

    setup_logging()
    from privacy_migration import run_legacy_purge
    try:
        run_legacy_purge()
    except Exception as e:
        log.critical("Legacy purge failed, not starting: %s", e)
        sys.exit(1)

    import config
    import metrics
    import sim_text
    from memory import PurgeService
    PurgeService(interval=config.MEMORY_PURGE_INTERVAL).start()
    audio_note = ""
    if args.input == "web":
        # Simulation: sound when it works, otherwise text; typing always works
        mode, audio_note = resolve_sim_audio(config.SIM_AUDIO)
        _set_env("SIM_AUDIO", mode)
        print(f"  {audio_note}", flush=True)      # terminal: what this start uses
    elif config.SIM_AUDIO == "auto":
        _set_env("SIM_AUDIO", "audio")
    text_mode = sim_text.enabled()
    if text_mode and args.input == "gpio":
        log.critical("SIM_AUDIO=text is for the simulation only, not with --input gpio")
        sys.exit(1)

    from channels import channel_from_env
    from help_alert import HelpService
    channel = channel_from_env()
    phone = None
    if args.input == "web":
        from sim_phone import SimPhone
        phone = SimPhone(config.SIM_PHONE_PORT, text_mode=text_mode,
                         host=config.SIM_PHONE_HOST, audio_note=audio_note)
        channel = _ShowOnPhone(channel, phone)
    # Real ring tone whenever there is a speaker (also on the simulated phone)
    ringer = SimulatedRinger() if text_mode or args.input == "keyboard" else AudioRinger()
    # Help speaks through a queue: the core loop never waits for audio
    voice = AnnouncementQueue(_speak, ringer=ringer)
    help_service = HelpService(channel, announce=voice.say_urgent,
                               senior_name=os.getenv("SENIOR_NAME", ""))
    help_service.run_worker()
    from family import run_sender
    run_sender(help_service.channel)
    core = Core(DialogSupervisor(), ringer, help_handler=help_service,
                announce=voice.say_and_wait,
                announce_handset=lambda text: voice.say_and_wait(text, output="handset"))
    core.tickers.append(StatusWriter(core, args.input, "text" if text_mode else "audio",
                                     type(channel.inner if phone else channel).__name__))
    core.tickers.append(_MetricsPurge())
    try:
        metrics.log_event("core_start")
    except Exception as e:
        log.error("Metrics event failed: %s", type(e).__name__)
    # Screen (T11): conversation as text, appointments, reminder, Help status
    screen = None
    if config.SCREEN_ENABLED or phone is not None:
        from screen import Screen, ScreenServer
        screen = Screen(core.phone_state,
                        ringing_text=lambda: (core.reminders.ringing.text
                                              if core.reminders and core.reminders.ringing else None),
                        help_status=help_service.screen_status)
        core.screen = screen
        if config.SCREEN_ENABLED:
            try:
                ScreenServer(screen, config.SCREEN_PORT).start()
            except OSError as e:
                log.error("Screen page not started: %s", e)   # the phone works without it

    def display(text: str, output: str = "handset") -> None:
        if phone is not None:
            phone.show(text, output)
        if screen is not None:
            screen.show(text, output)

    def display_heard(text: str) -> None:
        if phone is not None:
            phone.heard(text)
        if screen is not None:
            screen.heard(text)
    # What is said, as text (RAM only): from the core's own announcements and,
    # over the bus, from the dialog process
    sim_text.set_sink(display)
    core.supervisor.on_sim_say = display
    core.supervisor.on_sim_heard = display_heard
    if phone is not None:
        phone.screen = screen
        phone._state = core.phone_state
        try:
            phone.start(core.events)
        except (OSError, ValueError) as e:
            log.critical("Simulated telephone not started: %s", e)
            sys.exit(1)
    elif args.input == "gpio":
        GpioInput().start(core.events)
    else:
        KeyboardInput().start(core.events)
    signal.signal(signal.SIGTERM, lambda *a: setattr(core, "running", False))
    log.info("Core started (input %s, audio %s)", args.input, "text" if text_mode else "audio")
    core.run()
    log.info("Core stopped")
    if core.failed:
        try:
            metrics.log_event("input_failed")
        except Exception:
            pass
        sys.exit(1)   # systemd restarts the service


class _ShowOnPhone:
    """Channel wrapper for the simulation: what a contact receives also
    appears in the "Kontakt-Handy" panel of the phone page (RAM only)."""

    def __init__(self, inner, phone):
        self.inner = inner
        self.phone = phone

    def send_alert(self, address, text, alert_id):
        self.inner.send_alert(address, text, alert_id)
        self.phone.show(f"An {address}: {text}", "kanal")

    def send_message(self, address, text):
        self.inner.send_message(address, text)
        self.phone.show(f"Nachricht an {address}: {text}", "kanal")

    def __getattr__(self, name):
        return getattr(self.inner, name)


class _MetricsPurge:
    """Deletes metrics older than metrics.METRICS_RETENTION_DAYS, once an hour."""

    def __init__(self):
        self._last = 0.0

    def __call__(self) -> None:
        if time.monotonic() - self._last < 3600:
            return
        self._last = time.monotonic()
        import metrics
        metrics.purge()


if __name__ == "__main__":
    main()
