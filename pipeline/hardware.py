"""Hardware of the telephone, behind small interfaces.

Inputs (hook switch, buttons) become events in a queue for the core process.
Outputs are the ringer and the room speaker (A9: the conversation runs over
the handset; the speaker only rings, plus the Help confirmation, A13).

Two implementations:
- Simulated: keyboard commands on stdin (development and tests without a Pi).
- GPIO (PR 7): hook switch and six buttons on the Pi 5 via lgpio; the ringer
  plays a ring tone on the room speaker.
"""

import queue
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import Callable

from logging_config import get_logger

log = get_logger("hardware")

# Button names (decision B3, labels on the device in German)
BUTTONS = ("sprechen", "heute", "kalender", "rat", "familie", "hilfe")


@dataclass(frozen=True)
class InputEvent:
    """kind: "hook_off" (handset lifted), "hook_on" (hung up) or "button"."""
    kind: str
    name: str = ""


class Ringer:
    """Rings like a telephone over the room speaker."""

    def ring(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError


class SimulatedRinger(Ringer):
    def __init__(self):
        self.ringing = False

    def ring(self) -> None:
        if not self.ringing:
            log.info("[sim] RING RING")
        self.ringing = True

    def stop(self) -> None:
        self.ringing = False


class InputSource:
    """Pushes InputEvents into a queue."""

    def start(self, events: "queue.Queue[InputEvent]") -> None:
        raise NotImplementedError


KEYBOARD_HELP = (
    "Befehle: a = abheben, h = auflegen, "
    + ", ".join(BUTTONS) + " = Knopf, ok = Kontaktperson quittiert Help, q = beenden"
)


def parse_command(line: str) -> InputEvent | None:
    """Translate one keyboard line into an event (None if unknown)."""
    cmd = line.strip().lower()
    if cmd in ("a", "abheben"):
        return InputEvent("hook_off")
    if cmd in ("h", "auflegen"):
        return InputEvent("hook_on")
    if cmd in BUTTONS:
        return InputEvent("button", cmd)
    if cmd in ("ok", "quittieren"):
        return InputEvent("sim_ack")   # contact presses "Ich kümmere mich"
    if cmd in ("q", "quit"):
        return InputEvent("quit")
    return None


class KeyboardInput(InputSource):
    """Simulated phone: type commands on stdin."""

    def __init__(self, stream=None):
        self._stream = stream or sys.stdin

    def start(self, events: "queue.Queue[InputEvent]") -> None:
        def run():
            print(KEYBOARD_HELP, flush=True)
            for line in self._stream:
                event = parse_command(line)
                if event is None:
                    print(KEYBOARD_HELP, flush=True)
                    continue
                events.put(event)
                if event.kind == "quit":
                    return
            events.put(InputEvent("quit"))
        threading.Thread(target=run, name="keyboard", daemon=True).start()


def parse_button_pins(spec: str) -> dict[int, str]:
    """"sprechen:5,heute:6,..." -> {5: "sprechen", 6: "heute", ...}."""
    pins: dict[int, str] = {}
    for part in filter(None, (p.strip() for p in spec.split(","))):
        name, _, pin = part.partition(":")
        name = name.strip().lower()
        if name not in BUTTONS or not pin.strip().isdigit():
            raise ValueError(f"invalid button pin entry: {part!r}")
        if int(pin) in pins:
            raise ValueError(f"GPIO {pin} used twice")
        pins[int(pin)] = name
    missing = set(BUTTONS) - set(pins.values())
    if missing:
        raise ValueError(f"no GPIO for button(s): {sorted(missing)}")
    return pins


class GpioInput(InputSource):
    """Hook switch and buttons on the Pi 5 (lgpio), polled every 10 ms.

    A level must stay stable for GPIO_DEBOUNCE_MS before it counts, so
    contact bounce of the hook switch or a button never produces double
    events. If the handset is already lifted at start, hook_off is sent.
    """

    POLL_SECONDS = 0.01
    MAX_READ_FAILURES = 100      # about 1 s of failed reads -> give up, core exits

    def __init__(self, lgpio_module=None, chip: int | None = None,
                 hook_pin: int | None = None, offhook_level: int | None = None,
                 button_pins: dict[int, str] | None = None,
                 debounce_ms: int | None = None,
                 sleep: Callable[[float], None] = time.sleep,
                 monotonic: Callable[[], float] = time.monotonic):
        import config
        self._lgpio = lgpio_module
        self.chip = config.GPIO_CHIP if chip is None else chip
        self.hook_pin = config.HOOK_GPIO_PIN if hook_pin is None else hook_pin
        self.offhook_level = config.HOOK_OFFHOOK_LEVEL if offhook_level is None else offhook_level
        self.button_pins = button_pins or parse_button_pins(config.BUTTON_PINS)
        if self.hook_pin in self.button_pins:
            raise ValueError(f"GPIO {self.hook_pin} is used for the hook and a button")
        self.debounce = (config.GPIO_DEBOUNCE_MS if debounce_ms is None else debounce_ms) / 1000
        self.sleep = sleep
        self.monotonic = monotonic
        self.running = True

    def _open(self):
        lg = self._lgpio
        if lg is None:
            import lgpio as lg   # Raspberry Pi OS package
            self._lgpio = lg
        handle = lg.gpiochip_open(self.chip)
        for pin in [self.hook_pin, *self.button_pins]:
            lg.gpio_claim_input(handle, pin, lg.SET_PULL_UP)
        return handle

    def poll(self, handle, stable: dict, pending: dict, events) -> None:
        """One polling round (separate for tests)."""
        now = self.monotonic()
        for pin in [self.hook_pin, *self.button_pins]:
            level = self._lgpio.gpio_read(handle, pin)
            if level == stable[pin]:
                pending.pop(pin, None)
                continue
            since = pending.setdefault(pin, (level, now))
            if since[0] != level:
                pending[pin] = (level, now)
                continue
            if now - since[1] < self.debounce:
                continue
            stable[pin] = level
            pending.pop(pin, None)
            if pin == self.hook_pin:
                events.put(InputEvent("hook_off" if level == self.offhook_level else "hook_on"))
            elif level == 0:                       # pull-up: pressed = LOW
                events.put(InputEvent("button", self.button_pins[pin]))

    def start(self, events: "queue.Queue[InputEvent]") -> None:
        handle = self._open()
        stable = {pin: self._lgpio.gpio_read(handle, pin)
                  for pin in [self.hook_pin, *self.button_pins]}
        # Start as "on hook": a handset already lifted is reported after the
        # normal debounce, so a glitch at start-up does not start a call
        stable[self.hook_pin] = 1 - self.offhook_level

        def run():
            pending: dict = {}
            failures = 0
            try:
                while self.running:
                    try:
                        self.poll(handle, stable, pending, events)
                        failures = 0
                    except Exception as e:
                        failures += 1
                        if failures == 1:
                            log.error("GPIO read failed: %s", type(e).__name__)
                        if failures >= self.MAX_READ_FAILURES:
                            # Hook and Help can no longer be read: let the core
                            # exit so systemd restarts the whole device service
                            log.critical("GPIO unreadable, stopping")
                            events.put(InputEvent("input_failed"))
                            return
                    self.sleep(self.POLL_SECONDS)
            finally:
                try:
                    self._lgpio.gpiochip_close(handle)
                except Exception:
                    pass
        threading.Thread(target=run, name="gpio", daemon=True).start()
        log.info("GPIO input on chip %d: hook GPIO%d, buttons %s",
                 self.chip, self.hook_pin,
                 ", ".join(f"{n}=GPIO{p}" for p, n in sorted(self.button_pins.items())))


class AudioRinger(Ringer):
    """Rings over the room speaker (A5, A9) until stop() is called."""

    def __init__(self, command: Callable[[], list[str] | None] | None = None):
        self._command = command or self._default_command
        self._stop = threading.Event()
        self._paused = threading.Event()
        self._thread: threading.Thread | None = None
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()

    @staticmethod
    def _default_command() -> list[str] | None:
        from sounds import get_path
        from tts import player_command
        return player_command(get_path("ring"), output="speaker")

    @property
    def ringing(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def ring(self) -> None:
        if self.ringing:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="ringer", daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.is_set():
            if self._paused.is_set():
                self._stop.wait(0.05)          # an announcement uses the speaker
                continue
            try:
                cmd = self._command()
                if not cmd:
                    log.warning("No audio player for the ring tone")
                    return
                with self._lock:
                    if self._stop.is_set() or self._paused.is_set():
                        continue
                    self._proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                                  stderr=subprocess.DEVNULL)
                code = self._proc.wait()
                if code != 0 and not (self._stop.is_set() or self._paused.is_set()):
                    log.error("Ring tone player exited with %d", code)
                    self._stop.wait(1.0)
            except Exception as e:
                log.error("Ring tone failed: %s", type(e).__name__)
                self._stop.wait(1.0)

    def _kill_player(self) -> None:
        with self._lock:
            proc = self._proc
            if proc and proc.poll() is None:
                proc.terminate()
        if proc:
            try:
                proc.wait(timeout=2)
            except Exception:
                proc.kill()

    def pause(self) -> None:
        """Free the speaker for an announcement (Help goes first, A13)."""
        self._paused.set()
        self._kill_player()

    def resume(self) -> None:
        self._paused.clear()

    def stop(self) -> None:
        """Stops at once, also in the middle of a ring (handset lifted)."""
        self._stop.set()
        self._paused.clear()
        self._kill_player()
