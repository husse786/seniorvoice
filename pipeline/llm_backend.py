"""LLM backend abstraction with fallback chain and streaming support."""

import json
import os
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Generator
from urllib.parse import urlparse

from config import (
    LLM_BACKENDS, LLM_API_BASE, LLM_API_KEY, LLM_MODEL, LLM_TIMEOUT, ALLOW_CLOUD_LLM,
)
from logging_config import get_logger

log = get_logger("llm_backend")


@dataclass
class BackendConfig:
    """Configuration for a single LLM backend."""

    name: str
    api_base: str
    api_key: str
    model: str
    timeout: int


_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class CloudBackendRefused(RuntimeError):
    """Raised when a non-local LLM backend is configured but cloud is not allowed."""


def is_local(api_base: str) -> bool:
    """True if the API base URL points to this device (loopback only)."""
    host = (urlparse(api_base).hostname or "").lower()
    return host in _LOCAL_HOSTS


def _check_allowed(backend: BackendConfig) -> None:
    """Refuse non-local backends unless ALLOW_CLOUD_LLM is set (decision A1)."""
    if is_local(backend.api_base):
        return
    if not ALLOW_CLOUD_LLM:
        raise CloudBackendRefused(
            f"Backend '{backend.name}' is not local ({urlparse(backend.api_base).hostname}); "
            "refused because ALLOW_CLOUD_LLM is not set. Nothing was sent."
        )
    log.warning(
        "Backend '%s' is NOT local (%s): conversation data leaves the device "
        "(ALLOW_CLOUD_LLM=true). Never use this on a senior's device.",
        backend.name, urlparse(backend.api_base).hostname,
    )


# Local backends never go through an HTTP proxy: urllib would otherwise honour
# http_proxy/HTTPS_PROXY from the environment and send the conversation to the
# proxy host, even for a 127.0.0.1 URL.
_NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _open(backend: BackendConfig, req: urllib.request.Request, timeout: int):
    if is_local(backend.api_base):
        return _NO_PROXY_OPENER.open(req, timeout=timeout)
    return urllib.request.urlopen(req, timeout=timeout)


def _resolve_backends() -> list[BackendConfig]:
    """Parse LLM_BACKENDS env var into ordered list of BackendConfig.

    - "default": uses the global LLM_API_BASE/KEY/MODEL/TIMEOUT vars.
    - "a,b": resolves LLM_A_* and LLM_B_* env vars; missing values fall back
      to the global settings (local Ollama by default).
    """
    raw = LLM_BACKENDS.strip()
    if raw == "default":
        return [BackendConfig("default", LLM_API_BASE, LLM_API_KEY, LLM_MODEL, LLM_TIMEOUT)]

    backends = []
    for name in raw.split(","):
        name = name.strip().lower()
        prefix = f"LLM_{name.upper()}_"
        backends.append(BackendConfig(
            name=name,
            api_base=os.getenv(f"{prefix}API_BASE", LLM_API_BASE),
            api_key=os.getenv(f"{prefix}API_KEY", ""),
            model=os.getenv(f"{prefix}MODEL", LLM_MODEL),
            timeout=int(os.getenv(f"{prefix}TIMEOUT", str(LLM_TIMEOUT))),
        ))
    return backends


def _do_complete(backend: BackendConfig, messages: list[dict], timeout: int) -> str:
    """Execute a non-streaming completion against a single backend."""
    url = f"{backend.api_base}/chat/completions"
    payload = {"model": backend.model, "messages": messages, "stream": False}

    headers = {"Content-Type": "application/json"}
    if backend.api_key:
        headers["Authorization"] = f"Bearer {backend.api_key}"

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    with _open(backend, req, timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]


def _do_stream(backend: BackendConfig, messages: list[dict]) -> Generator[str, None, None]:
    """Open SSE connection and yield content deltas from a single backend."""
    url = f"{backend.api_base}/chat/completions"
    payload = {"model": backend.model, "messages": messages, "stream": True}

    headers = {"Content-Type": "application/json"}
    if backend.api_key:
        headers["Authorization"] = f"Bearer {backend.api_key}"

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    with _open(backend, req, backend.timeout) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8").strip()
            if not line.startswith("data: "):
                continue
            data = line[6:]
            if data == "[DONE]":
                return
            chunk = json.loads(data)
            delta = chunk["choices"][0]["delta"].get("content", "")
            if delta:
                yield delta


def complete(messages: list[dict], timeout_override: int | None = None) -> str:
    """Non-streaming completion with fallback chain.

    Tries each configured backend in order.
    Returns the first successful response text.
    Raises RuntimeError if all backends fail.
    """
    backends = _resolve_backends()
    last_error: Exception | None = None

    for backend in backends:
        timeout = timeout_override if timeout_override is not None else backend.timeout
        try:
            _check_allowed(backend)
        except CloudBackendRefused as e:
            log.error("%s", e)
            last_error = e
            continue
        try:
            log.debug("Trying backend '%s' (model=%s)", backend.name, backend.model)
            response = _do_complete(backend, messages, timeout)
            log.info("Backend '%s' responded (%d chars)", backend.name, len(response))
            return response
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
            log.warning("Backend '%s' failed: %s", backend.name, e)
            last_error = e
            continue

    raise RuntimeError(f"All LLM backends failed. Last error: {last_error}")


def stream(messages: list[dict]) -> Generator[str, None, None]:
    """Streaming completion with fallback chain.

    Yields token strings as they arrive from the first responding backend.
    Fallback happens only on connection errors (not mid-stream).
    """
    backends = _resolve_backends()
    last_error: Exception | None = None

    for backend in backends:
        try:
            _check_allowed(backend)
        except CloudBackendRefused as e:
            log.error("%s", e)
            last_error = e
            continue
        try:
            log.debug("Streaming from backend '%s' (model=%s)", backend.name, backend.model)
            yield from _do_stream(backend, messages)
            return
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
            log.warning("Stream backend '%s' failed to connect: %s", backend.name, e)
            last_error = e
            continue

    raise RuntimeError(f"All stream backends failed. Last error: {last_error}")
