"""Text mode of the simulated telephone (SIM_AUDIO=text).

For demos and tests without microphone and speaker: what the senior says is
typed on the simulated phone page, and what the device would say is shown
there instead of being spoken. Everything else (core, dialog, language model,
reminders, Help) runs unchanged.

Text only lives in RAM: typed sentences wait in a queue until the dialog takes
them, shown sentences go to the phone page, which forgets the conversation
when the handset is hung up. Nothing is written to a file or a log (A8).

Each process sets its own sink: the core shows sentences on the page
directly, the dialog process sends them to the core over the bus.
"""

import queue
import time
from typing import Callable

_sink: Callable[[str, str], None] | None = None
_inbox: "queue.Queue[str]" = queue.Queue()


def enabled() -> bool:
    from config import SIM_AUDIO
    return SIM_AUDIO == "text"


def set_sink(sink: Callable[[str, str], None] | None) -> None:
    global _sink
    _sink = sink


def show(text: str, output: str = "handset") -> None:
    """Instead of speaking: hand the sentence to the phone page."""
    if _sink is not None:
        _sink(text, output)


def put_input(text: str) -> None:
    _inbox.put(text)


def clear_input() -> None:
    while True:
        try:
            _inbox.get_nowait()
        except queue.Empty:
            return


def wait_input(still_active: Callable[[], bool], timeout: float,
               poll: float = 0.2) -> str:
    """Next typed sentence; "" when the call ended or nothing came in time."""
    deadline = time.monotonic() + timeout
    while still_active() and time.monotonic() < deadline:
        try:
            return _inbox.get(timeout=poll)
        except queue.Empty:
            continue
    return ""
