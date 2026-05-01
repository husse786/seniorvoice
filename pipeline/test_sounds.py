#!/usr/bin/env python3
"""Test sound generation locally (Mac or Pi). Plays chimes via afplay/paplay/aplay."""

import io
import wave
import subprocess
import shutil
import sys
import time
import numpy as np


def generate_tone(freq, duration, sample_rate=44100, volume=0.3):
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    samples = np.sin(2 * np.pi * freq * t) * volume
    fade_len = min(int(sample_rate * 0.01), len(samples) // 2)
    if fade_len > 0:
        samples[:fade_len] *= np.linspace(0, 1, fade_len)
        samples[-fade_len:] *= np.linspace(1, 0, fade_len)
    return (samples * 32767).astype(np.int16)


def to_wav(samples, sample_rate=44100):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples.tobytes())
    return buf.getvalue()


def play_wav(wav_bytes, label=""):
    import tempfile, os
    path = tempfile.mktemp(suffix=".wav")
    with open(path, "wb") as f:
        f.write(wav_bytes)

    # macOS: afplay, Linux: paplay or aplay
    for player in ["afplay", "paplay", "aplay"]:
        if shutil.which(player):
            print(f"  Playing '{label}' via {player}...")
            subprocess.run([player, path], check=True)
            os.unlink(path)
            return
    print(f"  No audio player found. Saved to {path}")


def main():
    rate = 44100

    # Listen chime: ascending C5 → E5
    print("\n1) Listen chime (ascending C5 → E5):")
    note1 = generate_tone(523.25, 0.12, rate)
    note2 = generate_tone(659.25, 0.15, rate)
    gap = np.zeros(int(rate * 0.03), dtype=np.int16)
    listen = to_wav(np.concatenate([note1, gap, note2]), rate)
    play_wav(listen, "listen")

    time.sleep(1)

    # Thinking chime: descending E5 → C5
    print("\n2) Thinking chime (descending E5 → C5):")
    note1 = generate_tone(659.25, 0.10, rate, volume=0.25)
    note2 = generate_tone(523.25, 0.13, rate, volume=0.25)
    gap = np.zeros(int(rate * 0.03), dtype=np.int16)
    thinking = to_wav(np.concatenate([note1, gap, note2]), rate)
    play_wav(thinking, "thinking")

    print("\nDone.")


if __name__ == "__main__":
    main()
