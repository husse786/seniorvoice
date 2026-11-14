"""LLM client — chat interface with optional streaming + per-sentence TTS."""

import re

from config import MEMORY_MAX_TURNS
from logging_config import get_logger, get_content_logger
from llm_backend import complete as llm_complete, stream as llm_stream

log = get_logger("llm")
content_log = get_content_logger("llm")

_BASE_SYSTEM_PROMPT = (
    "Du bist SeniorAgent, ein freundlicher und geduldiger Sprachassistent "
    "fuer aeltere Menschen (65+) in der Schweiz. Du sprichst Hochdeutsch, "
    "klar und einfach. Halte deine Antworten kurz (2-3 Saetze), es sei denn "
    "der Benutzer bittet um mehr Details. Sei warmherzig und hilfsbereit.\n"
    "\n"
    "Wichtige Regeln:\n"
    "- Verwende NIEMALS Emojis oder Sonderzeichen. Deine Antworten werden vorgelesen.\n"
    "- Sieze den Benutzer (verwende 'Sie', nicht 'du').\n"
    "- Wenn der Benutzer Fragen ueber sich selbst stellt (z.B. 'Wie heisse ich?', "
    "'Welchen Beruf habe ich?'), beantworte diese anhand der bekannten Informationen "
    "ueber den Benutzer. Verwechsle NICHT den Benutzer mit dir selbst.\n"
    "- Erfinde NIEMALS Informationen. Wenn du etwas nicht weisst, sage ehrlich: "
    "'Das weiss ich leider nicht.' Antworte lieber kurz und ehrlich als falsch."
)

_GREETING_INSTRUCTION = (
    "\nBegruesse den Benutzer herzlich — dies ist der Beginn einer neuen Sitzung."
)

_NO_GREETING_INSTRUCTION = (
    "\nDies ist eine laufende Sitzung. Begruesse den Benutzer NICHT erneut. "
    "Antworte direkt auf die Frage."
)

_SENTENCE_END = re.compile(r"[.!?]\s")


def build_system_prompt(facts_block: str = "", is_first_turn: bool = True) -> str:
    """Build the system prompt, optionally including known user facts."""
    parts = [_BASE_SYSTEM_PROMPT]
    parts.append(_GREETING_INSTRUCTION if is_first_turn else _NO_GREETING_INSTRUCTION)
    if facts_block:
        parts.append(f"\n{facts_block}")
    return "\n".join(parts)


def _build_messages(user_message: str, history: list[dict], facts_block: str) -> list[dict]:
    """Assemble the full messages list for the LLM call.

    Facts are placed both in the system prompt (for first-turn visibility)
    and repeated right before the user message on follow-up turns
    (small models lose early context as history grows).
    """
    is_first_turn = len(history) == 0
    system_prompt = build_system_prompt(facts_block, is_first_turn=is_first_turn)
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)

    # Re-inject facts near the user message so they stay in the model's
    # attention window even after several turns of conversation.
    if facts_block and not is_first_turn:
        user_message = f"[Erinnerung — {facts_block}]\n\n{user_message}"

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
                content_log.debug("Speaking sentence: %s", sentence[:80])
                speak(sentence)

            match = _SENTENCE_END.search(buffer)

    # Speak any remaining text
    remainder = buffer.strip()
    if remainder:
        content_log.debug("Speaking remainder: %s", remainder[:80])
        speak(remainder)

    log.debug("Streaming complete (%d chars total)", len(full_reply))
    history = _update_history(history, user_message, full_reply)
    return full_reply, history
