"""LLM client — OpenAI-compatible chat completions (Moonshot Kimi or local Ollama)."""

import json
import urllib.request
import urllib.error
from config import LLM_API_BASE, LLM_API_KEY, LLM_MODEL, LLM_TIMEOUT, MEMORY_MAX_TURNS
from logging_config import get_logger

log = get_logger("llm")

_BASE_SYSTEM_PROMPT = (
    "Du bist SeniorAgent, ein freundlicher und geduldiger Sprachassistent "
    "für ältere Menschen (65+) in der Schweiz. Du sprichst Hochdeutsch, "
    "klar und einfach. Halte deine Antworten kurz (2-3 Sätze), es sei denn "
    "der Benutzer bittet um mehr Details. Sei warmherzig und hilfsbereit."
)


def build_system_prompt(facts_block: str = "") -> str:
    """Build the system prompt, optionally including known user facts."""
    if not facts_block:
        return _BASE_SYSTEM_PROMPT
    return f"{_BASE_SYSTEM_PROMPT}\n\n{facts_block}"


def chat(user_message: str, history: list[dict] | None = None, facts_block: str = "") -> tuple[str, list[dict]]:
    """Send a message to the LLM and return (response, updated_history)."""
    if history is None:
        history = []

    system_prompt = build_system_prompt(facts_block)
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    url = f"{LLM_API_BASE}/chat/completions"

    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "stream": False,
    }

    headers = {"Content-Type": "application/json"}
    if LLM_API_KEY:
        headers["Authorization"] = f"Bearer {LLM_API_KEY}"

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=LLM_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            reply = data["choices"][0]["message"]["content"]
            log.debug("LLM response received (%d chars)", len(reply))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM API error {e.code}: {error_body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Cannot reach LLM API at {url}: {e.reason}") from e

    # Update history and trim to max turns
    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": reply})
    max_entries = MEMORY_MAX_TURNS * 2
    if len(history) > max_entries:
        history = history[-max_entries:]

    return reply, history
