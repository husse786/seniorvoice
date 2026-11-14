"""Decision A1: the language model runs locally only; cloud is off by default."""

import io
import json

import pytest

from conftest import patch_http


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _fake_urlopen(calls, answer="Guten Tag."):
    def urlopen(req, timeout=None):
        calls.append(req.full_url)
        body = {"choices": [{"message": {"content": answer}}]}
        return _FakeResponse(json.dumps(body).encode("utf-8"))
    return urlopen


def test_default_config_is_local_ollama(env):
    config = env.load("config")
    assert config.LLM_API_BASE == "http://127.0.0.1:11434/v1"
    assert "moonshot" not in config.LLM_API_BASE
    assert "kimi" not in config.LLM_MODEL
    assert config.ALLOW_CLOUD_LLM is False


def test_default_backends_are_all_local(env):
    backend = env.load("llm_backend")
    backends = backend._resolve_backends()
    assert backends
    assert all(backend.is_local(b.api_base) for b in backends)


def test_fs26_chain_without_values_stays_local(env):
    """FS26: LLM_BACKENDS=ollama,kimi alone fell back to Moonshot (finding B1)."""
    env.set(LLM_BACKENDS="ollama,kimi")
    backend = env.load("llm_backend")
    assert all(backend.is_local(b.api_base) for b in backend._resolve_backends())


@pytest.mark.parametrize("url,expected", [
    ("http://127.0.0.1:11434/v1", True),
    ("http://localhost:11434/v1", True),
    ("http://[::1]:11434/v1", True),
    ("https://api.moonshot.ai/v1", False),
    ("http://localhost.example.com/v1", False),
    ("http://127.0.0.1.nip.io/v1", False),
    ("http://192.168.1.20:11434/v1", False),
])
def test_is_local(env, url, expected):
    backend = env.load("llm_backend")
    assert backend.is_local(url) is expected


def test_cloud_backend_refused_and_nothing_sent(env, monkeypatch):
    env.set(LLM_API_BASE="https://api.moonshot.ai/v1", LLM_MODEL="kimi-k2.6")
    backend = env.load("llm_backend")
    calls = []
    patch_http(backend, monkeypatch, _fake_urlopen(calls))
    with pytest.raises(RuntimeError):
        backend.complete([{"role": "user", "content": "Hallo"}])
    with pytest.raises(RuntimeError):
        list(backend.stream([{"role": "user", "content": "Hallo"}]))
    assert calls == []


def test_cloud_in_chain_is_skipped_local_used(env, monkeypatch):
    env.set(
        LLM_BACKENDS="kimi,ollama",
        LLM_KIMI_API_BASE="https://api.moonshot.ai/v1",
    )
    backend = env.load("llm_backend")
    calls = []
    patch_http(backend, monkeypatch, _fake_urlopen(calls))
    assert backend.complete([{"role": "user", "content": "Hallo"}]) == "Guten Tag."
    assert calls == ["http://127.0.0.1:11434/v1/chat/completions"]


def test_cloud_only_with_explicit_flag(env, monkeypatch):
    env.set(LLM_API_BASE="https://api.moonshot.ai/v1", ALLOW_CLOUD_LLM="true")
    backend = env.load("llm_backend")
    calls = []
    patch_http(backend, monkeypatch, _fake_urlopen(calls))
    backend.complete([{"role": "user", "content": "Hallo"}])
    assert calls == ["https://api.moonshot.ai/v1/chat/completions"]


def test_memory_extraction_off_by_default(env, monkeypatch):
    memory = env.load("memory")
    called = []
    monkeypatch.setattr(memory, "_do_extract", lambda *a, **k: called.append(1) or True)
    memory.extract_and_store_facts([{"role": "user", "content": "Ich heisse Albert."}])
    memory.extract_facts_async([{"role": "user", "content": "Ich heisse Albert."}])
    assert called == []
    assert not (env.db_path.parent / "pending_extractions").exists()


def test_local_backend_ignores_http_proxy(env, monkeypatch):
    """A proxy from the environment must not receive local LLM traffic."""
    import http.server
    import threading

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            body = json.dumps({"choices": [{"message": {"content": "lokal"}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        for var in ("no_proxy", "NO_PROXY"):
            monkeypatch.delenv(var, raising=False)
        # A proxy that does not exist: any request through it fails
        for var in ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
            monkeypatch.setenv(var, "http://192.0.2.1:9")
        env.set(LLM_API_BASE=f"http://127.0.0.1:{server.server_port}/v1", LLM_TIMEOUT="3")
        backend = env.load("llm_backend")
        assert backend.complete([{"role": "user", "content": "Hallo"}]) == "lokal"
    finally:
        server.shutdown()
