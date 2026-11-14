"""Audio feedback sounds — generated programmatically with numpy."""

import io
import wave
import numpy as np
from pathlib import Path
from config import OUTPUT_DIR, SOUND_ENABLED
from logging_config import get_logger

log = get_logger("sounds")


def _generate_tone(freq: float, duration: float, sample_rate: int = 44100, volume: float = 0.3) -> np.ndarray:
    """Generate a sine-wave tone as int16 samples."""
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    # Apply fade-in/out (10ms) to avoid clicks
    samples = np.sin(2 * np.pi * freq * t) * volume
    fade_len = min(int(sample_rate * 0.01), len(samples) // 2)
    if fade_len > 0:
        fade_in = np.linspace(0, 1, fade_len)
        fade_out = np.linspace(1, 0, fade_len)
        samples[:fade_len] *= fade_in
        samples[-fade_len:] *= fade_out
    return (samples * 32767).astype(np.int16)


def _to_wav(samples: np.ndarray, sample_rate: int = 44100) -> bytes:
    """Convert int16 samples to WAV bytes."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples.tobytes())
    return buf.getvalue()


def _build_listen_chime() -> bytes:
    """Ascending two-note chime: C5 → E5."""
    rate = 44100
    note1 = _generate_tone(523.25, 0.12, rate)  # C5
    note2 = _generate_tone(659.25, 0.15, rate)  # E5
    gap = np.zeros(int(rate * 0.03), dtype=np.int16)
    return _to_wav(np.concatenate([note1, gap, note2]), rate)


def _build_thinking_chime() -> bytes:
    """Descending two-note chime: E5 → C5 (inverse of listen chime)."""
    rate = 44100
    note1 = _generate_tone(659.25, 0.10, rate, volume=0.25)  # E5
    note2 = _generate_tone(523.25, 0.13, rate, volume=0.25)  # C5
    gap = np.zeros(int(rate * 0.03), dtype=np.int16)
    return _to_wav(np.concatenate([note1, gap, note2]), rate)


def _build_ring() -> bytes:
    """One telephone ring cycle: two short bursts (440+480 Hz), then a pause."""
    rate = 44100

    def burst(seconds):
        a = _generate_tone(440.0, seconds, rate, volume=0.25).astype(np.int32)
        b = _generate_tone(480.0, seconds, rate, volume=0.25).astype(np.int32)
        return ((a + b) // 2).astype(np.int16)
    gap = np.zeros(int(rate * 0.2), dtype=np.int16)
    pause = np.zeros(int(rate * 2.0), dtype=np.int16)
    return _to_wav(np.concatenate([burst(0.4), gap, burst(0.4), pause]), rate)


# Cache paths
_SOUND_DIR = OUTPUT_DIR / "sounds"
_CACHE: dict[str, Path] = {}

_BUILDERS = {
    "listen": _build_listen_chime,
    "thinking": _build_thinking_chime,
    "ring": _build_ring,
}


def get_path(name: str) -> Path:
    """Get (and generate if needed) a cached sound file."""
    if name in _CACHE and _CACHE[name].exists():
        return _CACHE[name]

    if name not in _BUILDERS:
        raise ValueError(f"Unknown sound: {name}")

    _SOUND_DIR.mkdir(parents=True, exist_ok=True)
    path = _SOUND_DIR / f"{name}.wav"
    path.write_bytes(_BUILDERS[name]())
    _CACHE[name] = path
    return path


def play_sound(name: str) -> None:
    """Play a named feedback sound. No-op if sounds are disabled."""
    if not SOUND_ENABLED:
        return

    from tts import play
    try:
        path = get_path(name)
        play(path)
    except Exception as e:
        # Never let a feedback sound crash the pipeline
        log.warning("Failed to play '%s': %s", name, e)
