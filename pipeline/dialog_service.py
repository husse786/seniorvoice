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
import advice
import callback

setup_logging()
log = get_logger("dialog")

# Buttons answered in the dialog during a call (B3). "sprechen": the call is
# already a conversation.
SPOKEN_BUTTONS = ("familie", "heute", "kalender", "rat")

LLM_FAILED_REPLY = (
    "Entschuldigung, ich kann gerade nicht antworten. "
    "Bitte versuchen Sie es gleich nochmals."
)


def _senior_spoke(history: list[dict]) -> bool:
    """Only the device's opening in the history: nothing to remember."""
    return any(m.get("role") == "user" for m in history)


def _for_notes(history: list[dict], opening: list[dict]) -> list[dict]:
    """The opening (greeting with appointment, or reminder) is the device's
    own text from the local DB: it must not turn into notes (A8)."""
    return [m for m in history if not any(m is o for o in opening)]


class DialogService:
    def __init__(self, bus: Bus):
        self.bus = bus
        self.call_active = threading.Event()
        self.call_changed = threading.Event()
        self.running = True
        # Each lifting of the handset is a new call. A turn of an earlier call
        # that is still transcribing or waiting for the LLM must not continue.
        self.call_id = 0
        self.active = self.call_active.is_set   # replaced per call in run_call
        self.pending_button: str | None = None
        self.hint_given = False                 # emergency hint said in this call
        self.opened_with = ""                   # reminder the core spoke at pickup

    # --- messages from the core ---

    def on_message(self, msg: dict) -> None:
        kind = msg.get("type")
        if kind == "ping":
            self.bus.send("pong")
        elif kind == "sim_text":
            # Text mode of the simulation: a typed sentence (RAM only)
            import sim_text
            if isinstance(msg.get("text"), str):
                sim_text.put_input(msg["text"])
        elif kind == "call_start":
            self.opened_with = str(msg.get("opened_with") or "")[:500]
            self.call_id += 1
            self.call_active.set()
            self.call_changed.set()
        elif kind == "call_end":
            self.call_active.clear()
            self.call_changed.set()
        elif kind == "button" and msg.get("name") in SPOKEN_BUTTONS:
            self.pending_button = msg.get("name")
        elif kind == "closed":
            # Core is gone: stop, systemd/core will start us again
            self.running = False
            self.call_active.clear()
            self.call_changed.set()

    def state(self, state: str) -> None:
        self.bus.send("state", state=state)

    def hear(self) -> str:
        """One spoken answer of the senior (typed on the phone page in the
        text mode of the simulation)."""
        import sim_text
        if sim_text.enabled():
            from config import MAX_RECORD_SECONDS
            return sim_text.wait_input(self.active, timeout=MAX_RECORD_SECONDS)
        import audio_capture
        import stt
        typed = sim_text.take_input()
        if typed:
            return typed
        wav = audio_capture.record_until_silence()
        typed = sim_text.take_input()
        if typed:
            return typed
        text = stt.transcribe(wav)
        sim_text.heard(text)              # shown on the screen (RAM only)
        return text

    # --- conversation ---

    def notice(self, text: str) -> str | None:
        """R3/T12: emergency hint in the normal conversation too.

        Same word list as the Rat button, spoken before the LLM answers, at
        most once per call (talking about a fall over several turns must not
        repeat it each time). The Rat button always says it. Nothing is
        logged about it (it would reveal what was said).
        """
        if self.hint_given or not advice.is_emergency(text):
            return None
        self.hint_given = True
        return advice.EMERGENCY

    def say_notice(self, text: str) -> None:
        """Hint for spoken input outside the conversation (Family, callback)."""
        from tts import speak
        sentence = self.notice(text)
        if sentence and self.active():
            self.state("speaking")
            speak(sentence)

    def intercept(self, text: str) -> str | None:
        """Commands answered without the LLM."""
        if callback.is_cancel_request(text):
            callback.cancel_open_callbacks()
            return callback.CANCELLED
        return None

    def offer_callback(self) -> None:
        """A7: at most once a day, only a clear yes counts."""
        from datetime import datetime, timezone
        from tts import speak

        now = datetime.now(timezone.utc)
        if not self.active() or not callback.may_offer(now):
            return
        callback.reserve_offer(now)     # counts as asked today (unanswered = no)
        self.state("speaking")
        speak(callback.offer_question(now))
        self.state("listening")
        answer = self.hear() if self.active() else ""
        if not self.active():
            self.state("idle")          # hung up: no consent, nothing scheduled
            return
        self.say_notice(answer)
        _accepted, reply = callback.record_answer(answer, now)
        self.state("speaking")
        if self.active():
            speak(reply)
        self.state("idle")

    def family_message(self) -> None:
        """A4/M7: record, read back, send only after a clear yes."""
        import family
        from tts import speak
        from sounds import play_sound

        contact = family.recipient()
        self.state("speaking")
        if contact is None:
            speak(family.NO_RECIPIENT)
            self.state("idle")
            return
        speak(family.ASK)
        play_sound("listen")
        self.state("listening")
        text = self.hear().strip()
        if not self.active():
            self.state("idle")
            return
        self.say_notice(text)
        self.state("speaking")
        if not text:
            speak(family.NOTHING_HEARD)
            self.state("idle")
            return
        speak(family.READ_BACK.format(text=text, name=contact["name"]))
        self.state("listening")
        answer = self.hear()
        if not self.active():
            self.state("idle")          # hung up: send nothing, say nothing
            return
        self.state("speaking")
        if callback.is_clear_yes(answer):
            family.queue_message(text, contact)
            speak(family.SENT.format(name=contact["name"]))
        else:
            speak(family.NOT_SENT)
        self.state("idle")

    def read_calendar(self, button: str) -> None:
        """Heute / Kalender (B3): fixed sentences from the device, no LLM."""
        import appointments
        from tts import speak
        text = appointments.today_text() if button == "heute" else appointments.week_text()
        if self.active():
            self.state("speaking")
            speak(text)
        self.state("idle")

    def advice_question(self) -> None:
        """Rat (B2): one question, answered only from entered information.

        The question is neither stored nor logged and does not go into the
        conversation history, so it never reaches the notes either.
        """
        from tts import speak
        from sounds import play_sound

        self.state("speaking")
        speak(advice.ASK)
        play_sound("listen")
        self.state("listening")
        question = self.hear().strip()
        if not self.active():
            self.state("idle")
            return
        if not question:
            self.state("speaking")
            speak(advice.NOTHING_HEARD)
            self.state("idle")
            return
        # T12: the emergency hint comes from the word list and is spoken
        # before the model is asked (always here: it is an explicit question)
        emergency = advice.is_emergency(question)
        if emergency:
            self.hint_given = True
            self.state("speaking")
            speak(advice.EMERGENCY)
        if not self.active():
            self.state("idle")
            return
        self.state("thinking")
        item = advice.find_item(question)
        if self.active() and (item is not None or not emergency):
            self.state("speaking")
            speak(advice.answer_for(item, question))
        self.state("idle")

    def open_call(self, speak) -> list[dict]:
        """Start of a call. After a reminder the core has already spoken;
        otherwise the device greets from prompts/begruessung.txt. Whatever
        was said goes into the history (RAM) so the LLM knows what the
        senior's first answer refers to and does not greet again."""
        from config import GREETING_ON_PICKUP
        opened_with, self.opened_with = self.opened_with, ""
        if opened_with:
            return [{"role": "assistant", "content": opened_with}]
        if not GREETING_ON_PICKUP or not self.active():
            return []
        try:
            import greeting
            text = greeting.opening()
        except Exception as e:
            log.warning("Greeting failed: %s", type(e).__name__)
            return []
        self.state("speaking")
        speak(text)
        self.state("idle")
        return [{"role": "assistant", "content": text}]

    def run_call(self) -> None:
        """One call: turns until the handset is hung up."""
        from config import MEMORY_TIMEOUT
        from main import run_pipeline, _reload_facts
        from memory import extract_facts_async
        from tts import speak

        my_call = self.call_id
        self.hint_given = False
        import sim_text
        sim_text.clear_input()        # nothing typed before lifting counts

        def active() -> bool:
            return self.running and self.call_active.is_set() and self.call_id == my_call
        self.active = active

        _facts, facts_block = _reload_facts()
        history: list[dict] = self.open_call(speak)
        opening = list(history)
        last_speech = time.monotonic()
        while active():
            try:
                button, self.pending_button = self.pending_button, None
                if button == "familie":
                    self.family_message()
                    continue
                if button in ("heute", "kalender"):
                    self.read_calendar(button)
                    continue
                if button == "rat":
                    self.advice_question()
                    continue
                run_pipeline.last_text = ""
                history, pre_reset = run_pipeline(
                    use_pir=False, history=history, facts_block=facts_block,
                    trigger="handset", on_state=self.state,
                    # A button pressed mid-turn ends this turn: its transcript
                    # goes neither to the LLM nor into the history
                    still_active=lambda: active() and self.pending_button is None,
                    intercept=self.intercept,
                    notice=self.notice,
                )
                if pre_reset is not None:
                    extract_facts_async(_for_notes(pre_reset, opening),
                                        source=f"verbal-{int(time.time())}")
                if run_pipeline.last_text.strip():
                    last_speech = time.monotonic()
                    # Also after "Vergiss alles": deleted notes leave the prompt
                    _facts, facts_block = _reload_facts()
                elif _senior_spoke(history) and time.monotonic() - last_speech > MEMORY_TIMEOUT:
                    # Handset off the hook, nobody speaking: end the conversation
                    log.info("Conversation reset (silence %ds)", MEMORY_TIMEOUT)
                    extract_facts_async(_for_notes(history, opening),
                                        source=f"timeout-{int(time.time())}")
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
        if _senior_spoke(history):
            extract_facts_async(_for_notes(history, opening), source=f"call-{int(time.time())}")

    def run(self) -> None:
        from llm_backend import complete
        from config import MEMORY_PURGE_INTERVAL
        from memory import PurgeService

        import sim_text
        # Sentences go to the screen and phone page via the core (RAM only,
        # never to a file); in audio mode they are spoken as well
        sim_text.set_sink(lambda text, output: self.bus.send("sim_say", text=text, output=output))
        sim_text.set_heard_sink(lambda text: self.bus.send("sim_heard", text=text))
        self.bus.listen(self.on_message, name="core-bus")
        # Histories whose note extraction failed wait in this process's RAM;
        # expire them here too (the core's purge cannot reach this process).
        PurgeService(interval=MEMORY_PURGE_INTERVAL).start()
        self.state("loading")
        if not sim_text.enabled():
            from stt import get_model     # text mode needs no speech recognition
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
