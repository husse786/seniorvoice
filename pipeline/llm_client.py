"""LLM client — chat interface with optional streaming + per-sentence TTS."""

import re

from config import MEMORY_MAX_TURNS
from logging_config import get_logger, get_content_logger
from llm_backend import complete as llm_complete, stream as llm_stream

log = get_logger("llm")
content_log = get_content_logger("llm")

# Used only if prompts/persona.txt is missing or empty
_FALLBACK_SYSTEM_PROMPT = (
    "Du bist SeniorVoice, ein freundlicher und geduldiger Gesprächspartner "
    "für ältere Menschen (65+) in der Schweiz. Du sprichst Hochdeutsch, klar und "
    "einfach, und antwortest kurz. Sieze die Person. Verwende nie Emojis. "
    "Erfinde nie Informationen. Frage nie 'Wie kann ich Ihnen helfen?'."
)
_persona_cache: tuple[str, float, str] | None = None


def base_system_prompt() -> str:
    """Persona from prompts/persona.txt (editable without code; # = comment).
    Re-read when the file changes, so edits apply from the next sentence."""
    global _persona_cache
    from config import PROMPTS_DIR
    path = PROMPTS_DIR / "persona.txt"
    try:
        mtime = path.stat().st_mtime
        if _persona_cache is None or _persona_cache[:2] != (str(path), mtime):
            lines = path.read_text(encoding="utf-8").splitlines()
            text = "\n".join(l for l in lines if not l.lstrip().startswith("#")).strip()
            _persona_cache = (str(path), mtime, text)
        if _persona_cache[2]:
            return _persona_cache[2]
    except OSError as e:
        log.warning("Persona file not readable (%s), using fallback", type(e).__name__)
    return _FALLBACK_SYSTEM_PROMPT


# Only when the device did not open the call itself (GREETING_ON_PICKUP=false)
_GREETING_INSTRUCTION = (
    "\nDies ist der Beginn des Gesprächs. Begrüsse die Person kurz und herzlich "
    "und stelle eine kleine, konkrete Frage."
)

_NO_GREETING_INSTRUCTION = (
    "\nDas Gespräch läuft bereits. Begrüsse die Person NICHT erneut. "
    "Knüpfe an das Gesagte an."
)

_SENTENCE_END = re.compile(r"[.!?]\s")


def build_system_prompt(facts_block: str = "", is_first_turn: bool = True) -> str:
    """Build the system prompt, optionally including known user facts."""
    parts = [base_system_prompt()]
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


def chat_streaming(user_message: str, history: list[dict] | None = None, facts_block: str = "",
                   on_state=lambda state: None, still_active=lambda: True) -> tuple[str, list[dict]]:
    """Stream tokens from LLM and speak per sentence via TTS.

    Returns (full_reply, updated_history). TTS playback happens inline
    as sentences complete — the user hears the first sentence while
    the LLM is still generating the rest.

    on_state reports "speaking" during playback and "thinking" while waiting
    for tokens, so the core's hang watchdog measures a stalled LLM, not the
    length of the answer. If still_active() turns False (hung up), the
    stream is closed and nothing more is spoken.
    """
    from tts import speak

    if history is None:
        history = []

    messages = _build_messages(user_message, history, facts_block)

    buffer = ""
    full_reply = ""

    def say(sentence: str) -> None:
        on_state("speaking")
        speak(sentence)
        on_state("thinking")

    tokens = llm_stream(messages)
    try:
        for token in tokens:
            if not still_active():
                break
            buffer += token
            full_reply += token

            # Flush complete sentences to TTS
            match = _SENTENCE_END.search(buffer)
            while match and still_active():
                end_pos = match.end()
                sentence = buffer[:end_pos].strip()
                buffer = buffer[end_pos:]

                if sentence:
                    content_log.debug("Speaking sentence: %s", sentence[:80])
                    say(sentence)

                match = _SENTENCE_END.search(buffer)
    finally:
        close = getattr(tokens, "close", None)
        if close:
            close()

    # Speak any remaining text
    remainder = buffer.strip()
    if remainder and still_active():
        content_log.debug("Speaking remainder: %s", remainder[:80])
        say(remainder)

    log.debug("Streaming complete (%d chars total)", len(full_reply))
    history = _update_history(history, user_message, full_reply)
    return full_reply, history
