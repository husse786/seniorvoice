"""Configuration loaded from environment variables."""

import os
from pathlib import Path

# Audio
AUDIO_DEVICE_NAME = os.getenv("AUDIO_DEVICE_NAME", "C920")  # substring match
AUDIO_SAMPLE_RATE = int(os.getenv("AUDIO_SAMPLE_RATE", "16000"))
AUDIO_CHANNELS = 1
SILENCE_THRESHOLD = float(os.getenv("SILENCE_THRESHOLD", "0.02"))
SILENCE_DURATION = float(os.getenv("SILENCE_DURATION", "2.0"))  # seconds of silence to stop
MAX_RECORD_SECONDS = int(os.getenv("MAX_RECORD_SECONDS", "15"))

# STT (faster-whisper)
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "de")

# LLM (OpenAI-compatible API). Default: local Ollama on this device.
# Decision A1 (14.11.2026): the language model runs locally only. Conversation
# data must never leave the device by default.
LLM_API_BASE = os.getenv("LLM_API_BASE", "http://127.0.0.1:11434/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")  # not needed for local Ollama
LLM_MODEL = os.getenv("LLM_MODEL", "gemma3:1b")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "60"))  # seconds; local CPU models are slow

# Safety switch: backends that are not on this device (anything other than
# localhost) are refused unless this is explicitly set to true. Never set it
# on a device used by seniors.
ALLOW_CLOUD_LLM = os.getenv("ALLOW_CLOUD_LLM", "false").lower() in ("true", "1", "yes")

# Multi-backend LLM (fallback chain)
# "default" = use LLM_API_BASE/KEY/MODEL above
# "a,b" = try LLM_A_* first, then LLM_B_* (missing values fall back to the
#         LLM_API_BASE/MODEL above, i.e. to local Ollama)
LLM_BACKENDS = os.getenv("LLM_BACKENDS", "default")
LLM_STREAM = os.getenv("LLM_STREAM", "false").lower() in ("true", "1", "yes")

# TTS (Piper)
_default_voice = str(Path.home() / ".local/share/piper-voices/de_DE-thorsten-medium.onnx")
PIPER_VOICE = os.getenv("PIPER_VOICE", _default_voice)

# Conversation Memory
MEMORY_MAX_TURNS = int(os.getenv("MEMORY_MAX_TURNS", "10"))  # max user+assistant pairs kept
MEMORY_TIMEOUT = int(os.getenv("MEMORY_TIMEOUT", "300"))      # seconds of inactivity before reset

# Long-term memory notes (decision A8): kept at most 7 days, no health data.
MEMORY_EXTRACTION_ENABLED = os.getenv("MEMORY_EXTRACTION_ENABLED", "true").lower() in ("true", "1", "yes")
# Retention in days; values above 7 are capped at 7 (A8 sets 7 days as maximum).
MEMORY_RETENTION_DAYS = int(os.getenv("MEMORY_RETENTION_DAYS", "7"))
# How often the purge service deletes expired notes (seconds).
MEMORY_PURGE_INTERVAL = int(os.getenv("MEMORY_PURGE_INTERVAL", "3600"))

# Long-term Memory (SQLite)
MEMORY_DB_PATH = os.getenv("MEMORY_DB_PATH", str(Path.home() / "seniorvoice" / "seniorvoice.db"))

# Benchmark DB (defaults to same SQLite DB; override with DB_PATH for separate storage)
DB_PATH = os.getenv("DB_PATH", MEMORY_DB_PATH)

# PIR Sensor
PIR_GPIO_PIN = int(os.getenv("PIR_GPIO_PIN", "4"))
PIR_GPIO_CHIP = int(os.getenv("PIR_GPIO_CHIP", "4"))  # Pi 5 uses gpiochip4

# Audio Feedback
SOUND_ENABLED = os.getenv("SOUND_ENABLED", "true").lower() in ("true", "1", "yes")

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_DIR = Path(os.getenv("LOG_DIR", str(Path.home() / "seniorvoice" / "logs")))
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", str(5 * 1024 * 1024)))  # 5 MB
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))
# Conversation content (what the senior said, what the assistant answered) is
# never written to log files (decision A8). For development only, it can be
# shown on the console by setting LOG_CONTENT=true.
LOG_CONTENT = os.getenv("LOG_CONTENT", "false").lower() in ("true", "1", "yes")

# Paths
# Generated audio (spoken answers) is written to RAM (/dev/shm) when available,
# so it never lands on the SSD, and is deleted right after playback.
_default_output = "/dev/shm/seniorvoice" if Path("/dev/shm").is_dir() else "/tmp/seniorvoice"
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", _default_output))
