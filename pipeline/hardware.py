"""Hardware of the telephone, behind small interfaces.

Inputs (hook switch, buttons) become events in a queue for the core process.
Outputs are the ringer and the room speaker (A9: the conversation runs over
the handset; the speaker only rings, plus the Help confirmation, A13).

Two implementations:
- Simulated: keyboard commands on stdin (development and tests without a Pi).
- GPIO: added in PR 7 once the phone hardware is wired.
"""

import queue
import sys
import threading
from dataclasses import dataclass

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
    + ", ".join(BUTTONS) + " = Knopf, q = beenden"
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
