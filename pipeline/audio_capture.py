"""Record audio from the microphone (C920E webcam on the Pi, built-in on a Mac)."""

import numpy as np
import sounddevice as sd
import wave
import io
from config import (
    AUDIO_DEVICE_NAME,
    AUDIO_SAMPLE_RATE,
    AUDIO_CHANNELS,
    SILENCE_THRESHOLD,
    SILENCE_DURATION,
    MAX_RECORD_SECONDS,
)
from logging_config import get_logger

log = get_logger("audio")


def find_input_device() -> int | None:
    """Find the audio input device index by name substring match.

    Empty AUDIO_DEVICE_NAME: the system's default microphone (e.g. on a Mac
    for the simulated device).
    """
    if not AUDIO_DEVICE_NAME.strip():
        return None
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if AUDIO_DEVICE_NAME.lower() in dev["name"].lower() and dev["max_input_channels"] > 0:
            return i
    raise RuntimeError(
        f"No input device matching '{AUDIO_DEVICE_NAME}' found. "
        f"Available: {[d['name'] for d in devices if d['max_input_channels'] > 0]}"
    )


NO_SIGNAL_LEVEL = 0.002


def _level_hint(peak: float) -> None:
    """Tell the phone page when the microphone hears (almost) nothing."""
    import sim_text
    if peak < NO_SIGNAL_LEVEL:
        text = ("Das Mikrofon liefert kein Signal. Auf dem Mac: Systemeinstellungen, "
                "Datenschutz & Sicherheit, Mikrofon, Terminal einschalten und neu starten.")
    elif peak < SILENCE_THRESHOLD:
        text = (f"Das Mikrofon ist sehr leise (Pegel {peak:.3f}). Näher sprechen oder "
                f"SILENCE_THRESHOLD in .env tiefer setzen (jetzt {SILENCE_THRESHOLD}).")
    else:
        return
    log.warning("Microphone level low: %.4f", peak)
    sim_text.show(text, "hinweis")


def record_until_silence() -> bytes:
    """Record audio until silence is detected. Returns WAV bytes."""
    device_idx = find_input_device()
    log.debug("Recording from device %s", "default" if device_idx is None else device_idx)

    frames = []
    silent_chunks = 0
    peak = 0.0
    chunk_duration = 0.1  # 100ms chunks
    chunk_samples = int(AUDIO_SAMPLE_RATE * chunk_duration)
    max_chunks = int(MAX_RECORD_SECONDS / chunk_duration)
    silence_chunks_needed = int(SILENCE_DURATION / chunk_duration)

    with sd.InputStream(
        samplerate=AUDIO_SAMPLE_RATE,
        channels=AUDIO_CHANNELS,
        dtype="int16",
        device=device_idx,
        blocksize=chunk_samples,
    ) as stream:
        import sim_text
        for _ in range(max_chunks):
            if sim_text.has_input():
                # Typed on the simulated phone page: that answer counts instead
                break
            chunk, _ = stream.read(chunk_samples)
            frames.append(chunk.copy())

            # Check for silence (RMS amplitude)
            rms = np.sqrt(np.mean(chunk.astype(np.float32) ** 2)) / 32768.0
            peak = max(peak, float(rms))
            if rms < SILENCE_THRESHOLD:
                silent_chunks += 1
            else:
                silent_chunks = 0

            if silent_chunks >= silence_chunks_needed and len(frames) > silence_chunks_needed:
                log.debug("Silence detected after %.1fs", len(frames) * chunk_duration)
                break

    if not frames:
        if sim_text.has_input():
            return b""
        raise RuntimeError("No audio captured")

    audio_data = np.concatenate(frames)
    log.info("Captured %.1fs of audio (peak level %.4f)", len(audio_data) / AUDIO_SAMPLE_RATE, peak)
    _level_hint(peak)

    # Convert to WAV bytes
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(AUDIO_CHANNELS)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(AUDIO_SAMPLE_RATE)
        wf.writeframes(audio_data.tobytes())
    return buf.getvalue()


def save_wav(wav_bytes: bytes, path: str) -> None:
    """Save WAV bytes to a file."""
    with open(path, "wb") as f:
        f.write(wav_bytes)
    log.debug("Saved to %s", path)
