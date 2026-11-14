"""Text-to-Speech using Piper TTS; playback on the handset or the room speaker."""

import os
import subprocess
import shutil
import tempfile
from pathlib import Path
from config import PIPER_VOICE, OUTPUT_DIR, HANDSET_ALSA_DEVICE, SPEAKER_ALSA_DEVICE
from logging_config import get_logger, get_content_logger

log = get_logger("tts")
content_log = get_content_logger("tts")


def synthesize(text: str) -> Path:
    """Convert text to speech WAV file using Piper CLI.

    The file holds a spoken answer (conversation content). It goes to
    OUTPUT_DIR (RAM by default) and the caller must delete it after use.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="response-", suffix=".wav", dir=OUTPUT_DIR)
    os.close(fd)
    output_path = Path(name)

    piper_bin = shutil.which("piper")
    if piper_bin is None:
        raise RuntimeError("piper not found in PATH. Install with: pip install piper-tts")

    content_log.debug("Synthesizing: %s...", text[:80])
    try:
        result = subprocess.run(
            [piper_bin, "--model", PIPER_VOICE, "--output_file", str(output_path)],
            input=text,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except BaseException:
        output_path.unlink(missing_ok=True)
        raise

    if result.returncode != 0:
        output_path.unlink(missing_ok=True)
        # stderr may echo the input text, so it goes to the content log only
        content_log.debug("Piper stderr: %s", result.stderr)
        raise RuntimeError(f"Piper TTS failed (exit code {result.returncode})")

    log.debug("Saved to %s", output_path)
    return output_path


def player_command(wav_path: Path, output: str = "handset") -> list[str] | None:
    """Command that plays wav_path on the handset or the room speaker (A9).

    With HANDSET_ALSA_DEVICE / SPEAKER_ALSA_DEVICE set, aplay -D is used so
    the two outputs never mix; otherwise the system default (FS26 setup).
    """
    device = SPEAKER_ALSA_DEVICE if output == "speaker" else HANDSET_ALSA_DEVICE
    aplay = shutil.which("aplay")
    if device and aplay:
        return [aplay, "-q", "-D", device, str(wav_path)]
    paplay = shutil.which("paplay")
    if paplay:
        return [paplay, str(wav_path)]
    if aplay:
        return [aplay, "-q", str(wav_path)]
    return None


def play(wav_path: Path, output: str = "handset") -> None:
    """Play a WAV file on the handset (default) or the room speaker."""
    cmd = player_command(wav_path, output)
    if cmd is None:
        log.warning("No audio player found. WAV saved at: %s", wav_path)
        return
    log.debug("Playing on %s...", output)
    subprocess.run(cmd, timeout=30, check=True)
    log.debug("Playback done")


def speak(text: str, output: str = "handset") -> None:
    """Synthesize and play text, then delete the audio file (decision A8)."""
    wav_path = synthesize(text)
    try:
        play(wav_path, output)
    finally:
        wav_path.unlink(missing_ok=True)
