"""Test setup: every test gets its own temp paths and freshly imported modules.

pipeline/config.py reads environment variables at import time, so the
fixture sets the environment first and then (re)imports the modules.
"""

import importlib
import logging
import sys

import pytest

PIPELINE_MODULES = [
    "config", "logging_config", "llm_backend", "llm_client", "memory",
    "interaction_log", "privacy_migration", "main", "tts", "sounds",
    "audio_capture", "stt", "sensor", "bus", "hardware", "core_service",
    "dialog_service", "appointments",
]

# Environment variables that must not leak from the developer's shell
_ENV_TO_CLEAR = [
    "LLM_API_BASE", "LLM_API_KEY", "LLM_MODEL", "LLM_TIMEOUT", "LLM_BACKENDS",
    "LLM_STREAM", "ALLOW_CLOUD_LLM", "LOG_CONTENT", "LOG_LEVEL",
    "MEMORY_EXTRACTION_ENABLED", "OUTPUT_DIR", "MEMORY_DB_PATH", "LOG_DIR", "DB_PATH",
    "LLM_OLLAMA_API_BASE", "LLM_OLLAMA_MODEL", "LLM_KIMI_API_BASE", "LLM_KIMI_MODEL",
    "LLM_KIMI_API_KEY",
]


def _reset_logging():
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    content = logging.getLogger("seniorvoice.content")
    for handler in list(content.handlers):
        content.removeHandler(handler)


class PipelineEnv:
    def __init__(self, tmp_path, monkeypatch):
        self.tmp = tmp_path
        self.monkeypatch = monkeypatch
        self.db_path = tmp_path / "data" / "seniorvoice.db"
        self.log_dir = tmp_path / "logs"
        self.output_dir = tmp_path / "out"

    def set(self, **env):
        for key, value in env.items():
            self.monkeypatch.setenv(key, str(value))

    def load(self, name):
        """Import a pipeline module fresh, with the current environment."""
        for mod in PIPELINE_MODULES:
            sys.modules.pop(mod, None)
        _reset_logging()
        return importlib.import_module(name)

    def all_files(self):
        return [p for p in self.tmp.rglob("*") if p.is_file()]

    def files_containing(self, needle: str):
        data = needle.encode("utf-8")
        return [p for p in self.all_files() if data in p.read_bytes()]


def patch_http(backend_module, monkeypatch, urlopen):
    """Replace both HTTP paths of llm_backend (local no-proxy opener and urlopen)."""
    monkeypatch.setattr(backend_module.urllib.request, "urlopen", urlopen)
    fake_opener = type("FakeOpener", (), {"open": staticmethod(urlopen)})()
    monkeypatch.setattr(backend_module, "_NO_PROXY_OPENER", fake_opener)


@pytest.fixture
def env(tmp_path, monkeypatch):
    for key in _ENV_TO_CLEAR:
        monkeypatch.delenv(key, raising=False)
    e = PipelineEnv(tmp_path, monkeypatch)
    e.set(
        MEMORY_DB_PATH=e.db_path,
        LOG_DIR=e.log_dir,
        OUTPUT_DIR=e.output_dir,
        SOUND_ENABLED="false",
    )
    yield e
    _reset_logging()
    for mod in PIPELINE_MODULES:
        sys.modules.pop(mod, None)
