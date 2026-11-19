"""Text on the telephone: typed input and the shown conversation.

Text mode (SIM_AUDIO=text) is for demos and tests without microphone and
speaker. In the normal audio mode a sentence can still be typed on the
simulated phone page (it replaces the next spoken answer), and what is said
is shown as text on the device screen and the phone page (screen.py).

Original description of the text mode (SIM_AUDIO=text):

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
_heard_sink: Callable[[str], None] | None = None
_inbox: "queue.Queue[str]" = queue.Queue()


def enabled() -> bool:
    from config import SIM_AUDIO
    return SIM_AUDIO == "text"


def set_sink(sink: Callable[[str, str], None] | None) -> None:
    global _sink
    _sink = sink


def set_heard_sink(sink: Callable[[str], None] | None) -> None:
    global _heard_sink
    _heard_sink = sink


def show(text: str, output: str = "handset") -> None:
    """What the device says, as text for the screen and the phone page
    (in text mode instead of speaking, in audio mode in addition)."""
    if _sink is not None:
        try:
            _sink(text, output)
        except Exception:
            pass                      # the screen must never break speaking


def heard(text: str) -> None:
    """What the senior said (speech recognition), for the screen (RAM only)."""
    if _heard_sink is not None and text.strip():
        try:
            _heard_sink(text)
        except Exception:
            pass


def has_input() -> bool:
    """A typed sentence is waiting (ends a running recording early)."""
    return not _inbox.empty()


def take_input() -> str:
    """The waiting typed sentence, or "" (never blocks)."""
    try:
        return _inbox.get_nowait()
    except queue.Empty:
        return ""


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
