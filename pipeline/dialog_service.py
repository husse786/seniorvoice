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
import callback

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
        # Each lifting of the handset is a new call. A turn of an earlier call
        # that is still transcribing or waiting for the LLM must not continue.
        self.call_id = 0

    # --- messages from the core ---

    def on_message(self, msg: dict) -> None:
        kind = msg.get("type")
        if kind == "ping":
            self.bus.send("pong")
        elif kind == "call_start":
            self.call_id += 1
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

    def intercept(self, text: str) -> str | None:
        """Commands answered without the LLM."""
        if callback.is_cancel_request(text):
            callback.cancel_open_callbacks()
            return callback.CANCELLED
        return None

    def offer_callback(self) -> None:
        """A7: at most once a day, only a clear yes counts."""
        from datetime import datetime, timezone
        from audio_capture import record_until_silence
        from stt import transcribe
        from tts import speak

        now = datetime.now(timezone.utc)
        if not self.call_active.is_set() or not callback.may_offer(now):
            return
        self.state("speaking")
        speak(callback.offer_question(now))
        self.state("listening")
        answer = transcribe(record_until_silence()) if self.call_active.is_set() else ""
        _accepted, reply = callback.record_answer(answer, now)
        self.state("speaking")
        if self.call_active.is_set():
            speak(reply)
        self.state("idle")

    def run_call(self) -> None:
        """One call: turns until the handset is hung up."""
        from config import MEMORY_TIMEOUT
        from main import run_pipeline, _reload_facts
        from memory import extract_facts_async
        from tts import speak

        my_call = self.call_id

        def active() -> bool:
            return self.running and self.call_active.is_set() and self.call_id == my_call

        _facts, facts_block = _reload_facts()
        history: list[dict] = []
        last_speech = time.monotonic()
        while active():
            try:
                run_pipeline.last_text = ""
                history, pre_reset = run_pipeline(
                    use_pir=False, history=history, facts_block=facts_block,
                    trigger="handset", on_state=self.state,
                    still_active=active,
                    intercept=self.intercept,
                )
                if pre_reset is not None:
                    extract_facts_async(pre_reset, source=f"verbal-{int(time.time())}")
                if run_pipeline.last_text.strip():
                    last_speech = time.monotonic()
                    # Also after "Vergiss alles": deleted notes leave the prompt
                    _facts, facts_block = _reload_facts()
                elif history and time.monotonic() - last_speech > MEMORY_TIMEOUT:
                    # Handset off the hook, nobody speaking: end the conversation
                    log.info("Conversation reset (silence %ds)", MEMORY_TIMEOUT)
                    extract_facts_async(history, source=f"timeout-{int(time.time())}")
                    history = []
                    _facts, facts_block = _reload_facts()
                if callback.is_goodbye(run_pipeline.last_text):
                    self.offer_callback()
            except Exception as e:
                log.error("Turn failed: %s", type(e).__name__)
                if active():
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
        from config import MEMORY_PURGE_INTERVAL
        from memory import PurgeService

        self.bus.listen(self.on_message, name="core-bus")
        # Histories whose note extraction failed wait in this process's RAM;
        # expire them here too (the core's purge cannot reach this process).
        PurgeService(interval=MEMORY_PURGE_INTERVAL).start()
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
