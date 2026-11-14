#!/usr/bin/env python3
"""Dialog process: speech recognition, local LLM and speech output.

Started and supervised by core_service.py (decision A12). It receives
"call_start" when the handset is lifted and "call_end" when it is hung up,
answers pings, and reports its state so the core can detect an LLM hang.
A conversation lasts from lifting to hanging up (plus the inactivity
timeout); afterwards notes are extracted (7 days, A8) and the history is
dropped from RAM.
"""

import threading
import time

from logging_config import setup_logging, get_logger
from bus import Bus

setup_logging()
log = get_logger("dialog")

LLM_FAILED_REPLY = (
    "Entschuldigung, ich kann gerade nicht antworten. "
    "Bitte versuchen Sie es gleich nochmals."
)


class DialogService:
    def __init__(self, bus: Bus):
        self.bus = bus
        self.call_active = threading.Event()
        self.call_changed = threading.Event()
        self.running = True

    # --- messages from the core ---

    def on_message(self, msg: dict) -> None:
        kind = msg.get("type")
        if kind == "ping":
            self.bus.send("pong")
        elif kind == "call_start":
            self.call_active.set()
            self.call_changed.set()
        elif kind == "call_end":
            self.call_active.clear()
            self.call_changed.set()
        elif kind == "closed":
            # Core is gone: stop, systemd/core will start us again
            self.running = False
            self.call_active.clear()
            self.call_changed.set()

    def state(self, state: str) -> None:
        self.bus.send("state", state=state)

    # --- conversation ---

    def run_call(self) -> None:
        """One call: turns until the handset is hung up."""
        from main import run_pipeline, _reload_facts
        from memory import extract_facts_async
        from tts import speak

        _facts, facts_block = _reload_facts()
        history: list[dict] = []
        while self.call_active.is_set() and self.running:
            try:
                history, pre_reset = run_pipeline(
                    use_pir=False, history=history, facts_block=facts_block,
                    trigger="handset", on_state=self.state,
                    still_active=self.call_active.is_set,
                )
                if pre_reset is not None:
                    extract_facts_async(pre_reset, source=f"verbal-{int(time.time())}")
                    _facts, facts_block = _reload_facts()
            except Exception as e:
                log.error("Turn failed: %s", type(e).__name__)
                self.state("speaking")
                try:
                    speak(LLM_FAILED_REPLY)
                except Exception:
                    pass
                self.state("idle")
        # Hung up: remember notes (7 days), forget the conversation itself
        if history:
            extract_facts_async(history, source=f"call-{int(time.time())}")

    def run(self) -> None:
        from stt import get_model
        from llm_backend import complete

        self.bus.listen(self.on_message, name="core-bus")
        self.state("loading")
        get_model()
        try:
            complete([{"role": "user", "content": "Hallo"}], timeout_override=60)
        except Exception as e:
            log.warning("LLM warmup failed: %s", type(e).__name__)
        self.state("ready")
        log.info("Dialog ready")

        while self.running:
            self.call_changed.wait(timeout=1.0)
            self.call_changed.clear()
            if self.call_active.is_set():
                self.run_call()
                self.state("ready")


def main() -> None:
    DialogService(Bus.from_env()).run()


if __name__ == "__main__":
    main()
