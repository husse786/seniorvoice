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

# LLM (Moonshot Kimi API — OpenAI-compatible)
LLM_API_BASE = os.getenv("LLM_API_BASE", "https://api.moonshot.ai/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")  # MOONSHOT_API_KEY
LLM_MODEL = os.getenv("LLM_MODEL", "kimi-k2.5")

# TTS (Piper)
_default_voice = str(Path.home() / ".local/share/piper-voices/de_DE-thorsten-medium.onnx")
PIPER_VOICE = os.getenv("PIPER_VOICE", _default_voice)

# Conversation Memory
MEMORY_MAX_TURNS = int(os.getenv("MEMORY_MAX_TURNS", "10"))  # max user+assistant pairs kept
MEMORY_TIMEOUT = int(os.getenv("MEMORY_TIMEOUT", "300"))      # seconds of inactivity before reset

# Long-term Memory (SQLite)
MEMORY_DB_PATH = os.getenv("MEMORY_DB_PATH", str(Path.home() / "seniorvoice" / "seniorvoice.db"))

# PIR Sensor
PIR_GPIO_PIN = int(os.getenv("PIR_GPIO_PIN", "4"))
PIR_GPIO_CHIP = int(os.getenv("PIR_GPIO_CHIP", "4"))  # Pi 5 uses gpiochip4

# Paths
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/tmp/seniorvoice"))
