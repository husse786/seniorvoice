"""Text-to-Speech using Piper TTS, with playback via PulseAudio (Bluetooth speaker)."""

import subprocess
import shutil
from pathlib import Path
from config import PIPER_VOICE, OUTPUT_DIR
from logging_config import get_logger

log = get_logger("tts")


def synthesize(text: str) -> Path:
    """Convert text to speech WAV file using Piper CLI."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "response.wav"

    piper_bin = shutil.which("piper")
    if piper_bin is None:
        raise RuntimeError("piper not found in PATH. Install with: pip install piper-tts")

    log.debug("Synthesizing: %s...", text[:80])
    result = subprocess.run(
        [piper_bin, "--model", PIPER_VOICE, "--output_file", str(output_path)],
        input=text,
        capture_output=True,
        text=True,
        timeout=30,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Piper TTS failed: {result.stderr}")

    log.debug("Saved to %s", output_path)
    return output_path


def play(wav_path: Path) -> None:
    """Play a WAV file through the default PulseAudio sink (Bluetooth speaker)."""
    paplay = shutil.which("paplay")
    aplay = shutil.which("aplay")

    if paplay:
        cmd = [paplay, str(wav_path)]
    elif aplay:
        cmd = [aplay, str(wav_path)]
    else:
        log.warning("No audio player found. WAV saved at: %s", wav_path)
        return

    log.debug("Playing on speaker...")
    subprocess.run(cmd, timeout=30, check=True)
    log.debug("Playback done")


def speak(text: str) -> None:
    """Synthesize and play text."""
    wav_path = synthesize(text)
    play(wav_path)
