#!/usr/bin/env python3
"""SeniorVoice MVP Pipeline: PIR → Record → STT → Moonshot LLM → TTS → Speaker."""

import sys
import time
import argparse

from config import MEMORY_TIMEOUT
from memory import (
    load_facts, format_facts_for_prompt, extract_facts_async,
    extract_and_store_facts, retry_pending_extractions,
)

RESET_PHRASES = ["neue frage", "neues thema", "von vorne", "neues gespräch"]


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
        print(f"[pipeline] Loaded {len(facts)} fact(s) from memory")
    return facts, facts_block


def run_pipeline(
    use_pir: bool, history: list[dict], facts_block: str = ""
) -> tuple[list[dict], list[dict] | None]:
    """Run one full interaction cycle.

    Returns (updated_history, pre_reset_history_or_None).
    pre_reset_history is set when a verbal reset occurred, so the caller
    can trigger fact extraction on the old conversation.
    """
    from audio_capture import record_until_silence
    from stt import transcribe
    from llm_client import chat
    from tts import speak

    # Step 1: Wait for trigger
    if use_pir:
        from sensor import wait_for_motion
        wait_for_motion()
        # Small delay after motion to let the person settle
        time.sleep(0.5)
    else:
        input("\n[pipeline] Press ENTER to start recording...")

    # Step 2: Record audio
    print("\n--- Listening... ---")
    wav_bytes = record_until_silence()

    # Step 3: Transcribe
    print("\n--- Transcribing... ---")
    text = transcribe(wav_bytes)

    if not text.strip():
        print("[pipeline] No speech detected, skipping.")
        return history, None

    print(f"\n--- You said: {text} ---")

    # Step 3b: Check for verbal conversation reset
    pre_reset_history = None
    should_reset, cleaned_text = _check_reset(text)
    if should_reset:
        print("[pipeline] Conversation reset (verbal trigger)")
        pre_reset_history = list(history)  # snapshot for fact extraction
        history = []

    # Step 4: Get LLM response
    print("\n--- Thinking... ---")
    response, history = chat(cleaned_text, history, facts_block=facts_block)

    print(f"\n--- Response: {response} ---")

    # Step 5: Speak the response
    print("\n--- Speaking... ---")
    speak(response)

    print("\n--- Done ---\n")
    return history, pre_reset_history


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
    print(f"[pipeline] SeniorVoice MVP starting (trigger: {mode})")

    # Pre-load the STT model on startup
    from stt import get_model
    get_model()

    # Retry any pending extractions from previous failed runs
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
                        print(f"[pipeline] Conversation reset (timeout {MEMORY_TIMEOUT}s)")
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
                print(f"[pipeline] Error: {e}", file=sys.stderr)
                time.sleep(1)

            if args.once:
                break
    except KeyboardInterrupt:
        if history:
            print("\n[pipeline] Extracting facts before shutdown...")
            extract_and_store_facts(history, source=f"shutdown-{int(time.time())}")
        print("\n[pipeline] Shutting down.")


if __name__ == "__main__":
    main()
