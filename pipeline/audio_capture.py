"""Record audio from the Logitech C920E webcam microphone."""

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


def find_input_device() -> int:
    """Find the audio input device index by name substring match."""
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if AUDIO_DEVICE_NAME.lower() in dev["name"].lower() and dev["max_input_channels"] > 0:
            return i
    raise RuntimeError(
        f"No input device matching '{AUDIO_DEVICE_NAME}' found. "
        f"Available: {[d['name'] for d in devices if d['max_input_channels'] > 0]}"
    )


def record_until_silence() -> bytes:
    """Record audio until silence is detected. Returns WAV bytes."""
    device_idx = find_input_device()
    print(f"[audio] Recording from device {device_idx} ({sd.query_devices(device_idx)['name']})")

    frames = []
    silent_chunks = 0
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
        for _ in range(max_chunks):
            chunk, _ = stream.read(chunk_samples)
            frames.append(chunk.copy())

            # Check for silence (RMS amplitude)
            rms = np.sqrt(np.mean(chunk.astype(np.float32) ** 2)) / 32768.0
            if rms < SILENCE_THRESHOLD:
                silent_chunks += 1
            else:
                silent_chunks = 0

            if silent_chunks >= silence_chunks_needed and len(frames) > silence_chunks_needed:
                print(f"[audio] Silence detected after {len(frames) * chunk_duration:.1f}s")
                break

    if not frames:
        raise RuntimeError("No audio captured")

    audio_data = np.concatenate(frames)
    print(f"[audio] Captured {len(audio_data) / AUDIO_SAMPLE_RATE:.1f}s of audio")

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
    print(f"[audio] Saved to {path}")
