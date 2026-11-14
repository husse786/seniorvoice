#!/usr/bin/env python3
"""SeniorVoice MVP Pipeline: PIR -> Record -> STT -> LLM (Ollama/Kimi) -> TTS -> Speaker."""

import re
import sys
import time
import argparse

from logging_config import setup_logging, get_logger, get_content_logger
from config import MEMORY_TIMEOUT, LLM_STREAM, MEMORY_PURGE_INTERVAL
from memory import (
    load_facts, format_facts_for_prompt, extract_facts_async,
    extract_and_store_facts, retry_pending_extractions, forget_all, PurgeService,
)
from sounds import play_sound
from interaction_log import log_interaction
from privacy_migration import run_legacy_purge

setup_logging()
log = get_logger("pipeline")
# Conversation content: console only, off by default, never in log files (A8)
content_log = get_content_logger("pipeline")

RESET_PHRASES = ["neue frage", "neues thema", "von vorne", "neues gespräch"]

# "Vergiss das" (decision A8). Open question F3: current proposal is
# - FORGET_THIS: the current conversation is not remembered (no notes from it)
# - FORGET_ALL: all notes are deleted immediately
# Answered with fixed sentences, without the LLM.
FORGET_ALL_PHRASES = ["vergiss alles", "vergessen sie alles", "lösch alles", "löschen sie alles"]
FORGET_THIS_PHRASES = ["vergiss das", "vergessen sie das", "lösch das", "löschen sie das"]
FORGET_ALL_REPLY = "In Ordnung. Ich habe alles vergessen, was ich mir über Sie gemerkt habe."
FORGET_THIS_REPLY = "In Ordnung. Ich merke mir nichts aus diesem Gespräch."


def _has_phrase(lower: str, phrases: list[str]) -> bool:
    """Phrase present and not negated ("Vergiss das nicht" is no command)."""
    return any(
        re.search(rf"\b{re.escape(p)}\b(?!\s+nicht)", lower) for p in phrases
    )


def _check_forget(text: str) -> str | None:
    """Return "all", "this" or None for a spoken forget command."""
    lower = text.lower()
    if _has_phrase(lower, FORGET_ALL_PHRASES):
        return "all"
    if _has_phrase(lower, FORGET_THIS_PHRASES):
        return "this"
    return None


def _check_reset(text: str) -> tuple[bool, str]:
    """Check if the user wants to reset the conversation.

    Returns (should_reset, cleaned_text).
    """
    lower = text.lower()
    for phrase in RESET_PHRASES:
        if phrase in lower:
            # Remove the reset phrase, keep the rest (if any)
            cleaned = lower.replace(phrase, "").strip(" .,!?")
            return True, cleaned if cleaned else text
    return False, text


def _reload_facts() -> tuple[list[dict], str]:
    """Load facts from DB and format for prompt."""
    facts = load_facts()
    facts_block = format_facts_for_prompt(facts)
    if facts:
        log.info("Loaded %d fact(s) from memory", len(facts))
    return facts, facts_block


def _no_state(state: str) -> None:
    pass


def run_pipeline(
    use_pir: bool, history: list[dict], facts_block: str = "",
    trigger: str | None = None, on_state=_no_state,
    still_active=lambda: True,
    intercept=None,
) -> tuple[list[dict], list[dict] | None]:
    """Run one full interaction cycle.

    trigger: None = wait for PIR/ENTER (FS26 mode); "handset" = the caller
    (dialog process) already knows the handset is lifted, start right away.
    on_state(state) reports "listening", "thinking", "speaking", "idle" to
    the core process (LLM hang detection). still_active() is checked after
    transcription: if the senior hung up meanwhile, nothing is sent to the LLM,
    and again before each spoken answer. intercept(text) may return a fixed
    reply (e.g. cancel a callback); then the LLM is skipped. The last
    transcript is kept in RAM as
    run_pipeline.last_text for the caller (never stored).

    Returns (updated_history, pre_reset_history_or_None).
    pre_reset_history is set when a verbal reset occurred, so the caller
    can trigger fact extraction on the old conversation.
    """
    from audio_capture import record_until_silence
    from stt import transcribe
    from llm_client import chat, chat_streaming
    from tts import speak

    trigger_type = trigger or ("pir" if use_pir else "keyboard")
    t_start = time.perf_counter()
    stt_ms = llm_ms = tts_ms = None

    # Step 1: Wait for trigger
    if trigger is not None:
        pass  # handset already lifted
    elif use_pir:
        from sensor import wait_for_motion
        wait_for_motion()
        # Small delay after motion to let the person settle
        time.sleep(0.5)
    else:
        input("\n[Press ENTER to start recording...]")

    play_sound("listen")

    # Step 2: Record audio
    on_state("listening")
    log.info("Listening...")
    wav_bytes = record_until_silence()

    # Step 3: Transcribe
    log.info("Transcribing...")
    t_stt = time.perf_counter()
    text = transcribe(wav_bytes)
    stt_ms = int((time.perf_counter() - t_stt) * 1000)

    run_pipeline.last_text = text
    if not still_active():
        on_state("idle")
        return history, None

    if not text.strip():
        on_state("idle")
        log.info("No speech detected, skipping")
        log_interaction(trigger_type=trigger_type, error="no_speech")
        return history, None

    content_log.debug("User said: %s", text)

    # Step 3a: "Vergiss das" / "Vergiss alles" (A8): handled without the LLM
    forget = _check_forget(text)
    if forget is not None:
        if forget == "all":
            forget_all()
            reply = FORGET_ALL_REPLY
        else:
            reply = FORGET_THIS_REPLY
        log.info("Forget command (%s)", forget)
        on_state("speaking")
        speak(reply)
        on_state("idle")
        # Empty history and no pre-reset snapshot: nothing is extracted
        return [], None

    # Step 3a2: commands handled by the caller without the LLM
    reply = intercept(text) if intercept else None
    if reply:
        on_state("speaking")
        speak(reply)
        on_state("idle")
        return history, None

    # Step 3b: Check for verbal conversation reset
    pre_reset_history = None
    should_reset, cleaned_text = _check_reset(text)
    if should_reset:
        log.info("Conversation reset (verbal trigger)")
        pre_reset_history = list(history)  # snapshot for fact extraction
        history = []

    # Step 4: Get LLM response (+ Step 5 if streaming)
    play_sound("thinking")
    on_state("thinking")
    log.info("Thinking...")
    t_llm = time.perf_counter()

    if LLM_STREAM:
        # Streaming: TTS happens per-sentence inside chat_streaming
        response, history = chat_streaming(cleaned_text, history, facts_block=facts_block,
                                           on_state=on_state, still_active=still_active)
        llm_ms = int((time.perf_counter() - t_llm) * 1000)
        tts_ms = 0  # included in llm_ms for streaming mode
    else:
        response, history = chat(cleaned_text, history, facts_block=facts_block)
        llm_ms = int((time.perf_counter() - t_llm) * 1000)

        # Step 5: Speak the response (non-streaming), unless hung up meanwhile
        t_tts = time.perf_counter()
        if still_active():
            on_state("speaking")
            log.info("Speaking...")
            speak(response)
        tts_ms = int((time.perf_counter() - t_tts) * 1000)

    content_log.debug("Response: %s", response)

    on_state("idle")
    total_ms = int((time.perf_counter() - t_start) * 1000)
    log.info("Interaction complete (stt=%dms, llm=%dms, tts=%dms, total=%dms)",
             stt_ms, llm_ms, tts_ms, total_ms)

    # Log interaction metrics to SQLite (no conversation text, decision A8)
    log_interaction(
        trigger_type=trigger_type,
        stt_duration_ms=stt_ms,
        llm_duration_ms=llm_ms,
        tts_duration_ms=tts_ms,
        total_duration_ms=total_ms,
    )

    return history, pre_reset_history


run_pipeline.last_text = ""


def main():
    parser = argparse.ArgumentParser(description="SeniorVoice MVP Pipeline")
    parser.add_argument(
        "--no-pir",
        action="store_true",
        help="Use keyboard trigger instead of PIR sensor",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one interaction cycle and exit",
    )
    args = parser.parse_args()

    use_pir = not args.no_pir
    mode = "PIR sensor" if use_pir else "keyboard (ENTER)"
    log.info("SeniorVoice starting (trigger: %s)", mode)

    # One-time removal of conversation data stored by the FS26 version
    # (decision F2, 14.11.2026). Idempotent; does nothing after the first run.
    try:
        run_legacy_purge()
    except Exception as e:
        log.critical("Legacy purge failed, not starting: %s", e)
        sys.exit(1)

    # Pre-load the STT model on startup
    from stt import get_model
    get_model()

    # Warm up LLM backend (Ollama keeps models in RAM after first call)
    from llm_backend import complete as _llm_warmup
    try:
        log.info("Warming up LLM backend...")
        _llm_warmup([{"role": "user", "content": "Hallo"}], timeout_override=60)
        log.info("LLM backend ready")
    except Exception as e:
        log.warning("LLM warmup failed (will retry on first interaction): %s", e)

    # Delete expired notes now and every hour (7-day retention, A8)
    purge_service = PurgeService(interval=MEMORY_PURGE_INTERVAL)
    purge_service.start()
    retry_pending_extractions()

    # Load persistent memory
    facts, facts_block = _reload_facts()

    history: list[dict] = []
    last_interaction = time.time()

    try:
        while True:
            try:
                # Timeout: reset history after inactivity
                if time.time() - last_interaction > MEMORY_TIMEOUT:
                    if history:
                        log.info("Conversation reset (timeout %ds)", MEMORY_TIMEOUT)
                        extract_facts_async(history, source=f"timeout-{int(time.time())}")
                        history = []
                        facts, facts_block = _reload_facts()

                history, pre_reset = run_pipeline(
                    use_pir=use_pir, history=history, facts_block=facts_block
                )
                last_interaction = time.time()

                # Verbal reset: extract facts from the old conversation
                if pre_reset is not None:
                    extract_facts_async(pre_reset, source=f"verbal-{int(time.time())}")
                    facts, facts_block = _reload_facts()

            except KeyboardInterrupt:
                raise
            except Exception as e:
                log.error("Pipeline error: %s", e, exc_info=True)
                time.sleep(1)

            if args.once:
                break
    except KeyboardInterrupt:
        if history:
            log.info("Extracting facts before shutdown...")
            extract_and_store_facts(history, source=f"shutdown-{int(time.time())}")
        log.info("Shutting down.")


if __name__ == "__main__":
    main()
