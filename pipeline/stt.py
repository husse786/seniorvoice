"""Speech-to-Text using faster-whisper."""

import io
import wave
import numpy as np
from faster_whisper import WhisperModel
from config import WHISPER_MODEL, WHISPER_DEVICE, WHISPER_LANGUAGE

_model = None


def get_model() -> WhisperModel:
    """Lazy-load the Whisper model."""
    global _model
    if _model is None:
        print(f"[stt] Loading whisper model '{WHISPER_MODEL}' on {WHISPER_DEVICE}...")
        _model = WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE, compute_type="int8")
        print("[stt] Model loaded")
    return _model


def transcribe(wav_bytes: bytes) -> str:
    """Transcribe WAV audio bytes to text."""
    # Convert WAV bytes to float32 numpy array
    buf = io.BytesIO(wav_bytes)
    with wave.open(buf, "rb") as wf:
        raw = wf.readframes(wf.getnframes())
        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

    model = get_model()
    segments, info = model.transcribe(audio, language=WHISPER_LANGUAGE, beam_size=5)

    text = " ".join(seg.text.strip() for seg in segments)
    print(f"[stt] Transcribed ({info.language}, {info.language_probability:.0%}): {text}")
    return text
