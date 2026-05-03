"""LLM client — chat interface with optional streaming + per-sentence TTS."""

import re

from config import MEMORY_MAX_TURNS
from logging_config import get_logger
from llm_backend import complete as llm_complete, stream as llm_stream

log = get_logger("llm")

_BASE_SYSTEM_PROMPT = (
    "Du bist SeniorAgent, ein freundlicher und geduldiger Sprachassistent "
    "für ältere Menschen (65+) in der Schweiz. Du sprichst Hochdeutsch, "
    "klar und einfach. Halte deine Antworten kurz (2-3 Sätze), es sei denn "
    "der Benutzer bittet um mehr Details. Sei warmherzig und hilfsbereit."
)

_SENTENCE_END = re.compile(r"[.!?]\s")


def build_system_prompt(facts_block: str = "") -> str:
    """Build the system prompt, optionally including known user facts."""
    if not facts_block:
        return _BASE_SYSTEM_PROMPT
    return f"{_BASE_SYSTEM_PROMPT}\n\n{facts_block}"


def _build_messages(user_message: str, history: list[dict], facts_block: str) -> list[dict]:
    """Assemble the full messages list for the LLM call."""
    system_prompt = build_system_prompt(facts_block)
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})
    return messages


def _update_history(history: list[dict], user_message: str, reply: str) -> list[dict]:
    """Append the exchange to history and trim to max turns."""
    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": reply})
    max_entries = MEMORY_MAX_TURNS * 2
    if len(history) > max_entries:
        history = history[-max_entries:]
    return history


def chat(user_message: str, history: list[dict] | None = None, facts_block: str = "") -> tuple[str, list[dict]]:
    """Send a message to the LLM (non-streaming) and return (response, updated_history)."""
    if history is None:
        history = []

    messages = _build_messages(user_message, history, facts_block)
    reply = llm_complete(messages)
    log.debug("LLM response received (%d chars)", len(reply))

    history = _update_history(history, user_message, reply)
    return reply, history


def chat_streaming(user_message: str, history: list[dict] | None = None, facts_block: str = "") -> tuple[str, list[dict]]:
    """Stream tokens from LLM and speak per sentence via TTS.

    Returns (full_reply, updated_history). TTS playback happens inline
    as sentences complete — the user hears the first sentence while
    the LLM is still generating the rest.
    """
    from tts import speak

    if history is None:
        history = []

    messages = _build_messages(user_message, history, facts_block)

    buffer = ""
    full_reply = ""

    for token in llm_stream(messages):
        buffer += token
        full_reply += token

        # Flush complete sentences to TTS
        match = _SENTENCE_END.search(buffer)
        while match:
            end_pos = match.end()
            sentence = buffer[:end_pos].strip()
            buffer = buffer[end_pos:]

            if sentence:
                log.debug("Speaking sentence: %s", sentence[:80])
                speak(sentence)

            match = _SENTENCE_END.search(buffer)

    # Speak any remaining text
    remainder = buffer.strip()
    if remainder:
        log.debug("Speaking remainder: %s", remainder[:80])
        speak(remainder)

    log.debug("Streaming complete (%d chars total)", len(full_reply))
    history = _update_history(history, user_message, full_reply)
    return full_reply, history
