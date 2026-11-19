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

# Technical metrics (timings, error codes, service events, benchmarks) live in a
# database of their own, next to the senior's data but separate from it. Grafana
# and the health view read only this file, never seniorvoice.db (notes,
# appointments, Help). FS26 kept everything in one file.
METRICS_DB_PATH = os.getenv("METRICS_DB_PATH", str(Path(MEMORY_DB_PATH).parent / "metrics.db"))

# Benchmark DB (defaults to the metrics database)
DB_PATH = os.getenv("DB_PATH", METRICS_DB_PATH)

# PIR Sensor
PIR_GPIO_PIN = int(os.getenv("PIR_GPIO_PIN", "4"))
PIR_GPIO_CHIP = int(os.getenv("PIR_GPIO_CHIP", "4"))  # Pi 5 uses gpiochip4

# Telephone hardware (PR 7). Hook switch NC to GND with pull-up: off-hook = HIGH
# (FS26 how-to_analog-telephone.md). Buttons to GND with pull-up: pressed = LOW.
# Pi 5: gpiochip4 on older kernels, gpiochip0 on newer Raspberry Pi OS.
GPIO_CHIP = int(os.getenv("GPIO_CHIP", "4"))
HOOK_GPIO_PIN = int(os.getenv("HOOK_GPIO_PIN", "17"))
HOOK_OFFHOOK_LEVEL = int(os.getenv("HOOK_OFFHOOK_LEVEL", "1"))
BUTTON_PINS = os.getenv(
    "BUTTON_PINS", "sprechen:5,heute:6,kalender:13,rat:19,familie:26,hilfe:21")
GPIO_DEBOUNCE_MS = int(os.getenv("GPIO_DEBOUNCE_MS", "30"))
# ALSA devices (aplay -D). Conversation over the handset, ringing and the Help
# confirmation over the room speaker (A9, A13). Empty = system default.
HANDSET_ALSA_DEVICE = os.getenv("HANDSET_ALSA_DEVICE", "")
SPEAKER_ALSA_DEVICE = os.getenv("SPEAKER_ALSA_DEVICE", "")

# Device API for the portal (PR 10, B4). Listens only on the tunnel address;
# without a token hash it does not start. AUDIT_RETENTION_DAYS: proposal (DS-07 open).
DEVICE_API_HOST = os.getenv("DEVICE_API_HOST", "127.0.0.1")
DEVICE_API_PORT = int(os.getenv("DEVICE_API_PORT", "8770"))
DEVICE_API_TOKEN_SHA256 = os.getenv("DEVICE_API_TOKEN_SHA256", "").strip().lower()
AUDIT_RETENTION_DAYS = int(os.getenv("AUDIT_RETENTION_DAYS", "30"))

# Simulated telephone (development and demo without the phone hardware).
# SIM_AUDIO=text: the senior's words are typed on the simulated phone page and
# the device's answers are shown there instead of spoken (no microphone, no
# speaker needed). Default "audio": microphone and speaker as on the device.
SIM_AUDIO = os.getenv("SIM_AUDIO", "audio").strip().lower()
if SIM_AUDIO not in ("audio", "text"):
    SIM_AUDIO = "audio"
# Page of the simulated phone; always bound to 127.0.0.1 (this computer only)
SIM_PHONE_PORT = int(os.getenv("SIM_PHONE_PORT", "8771"))
# Where the simulated phone page listens. 127.0.0.1 = only this computer. On a
# Pi without screen: its WireGuard address, so the team laptop opens the page
# through the tunnel (never all interfaces: the page has no login).
SIM_PHONE_HOST = os.getenv("SIM_PHONE_HOST", "127.0.0.1").strip()
# Input when core_service.py is started without --input (systemd unit: gpio;
# on the Pi before the telephone is wired: web)
SENIORVOICE_INPUT = os.getenv("SENIORVOICE_INPUT", "keyboard").strip().lower()

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

# Live state of the core for the health view (RAM, rewritten every few seconds)
STATUS_FILE = OUTPUT_DIR / "core_status.json"
