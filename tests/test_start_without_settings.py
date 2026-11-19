"""Starting must work without touching .env, also with a .env from an earlier
setup (SIM_AUDIO=text was written there by the first guide)."""

import importlib.util
import os
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _upgrade_env():
    spec = importlib.util.spec_from_file_location("upgrade_env", ROOT / "scripts" / "upgrade_env.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


OLD_ENV = """LLM_MODEL=gemma3:1b
AUDIO_DEVICE_NAME=
SIM_AUDIO=text
DEVICE_API_TOKEN_SHA256=abc123
SENIOR_NAME="Frau Keller"
"""


def test_old_text_mode_is_switched_off_with_backup(tmp_path):
    up = _upgrade_env()
    env = tmp_path / ".env"
    env.write_text(OLD_ENV)
    messages = up.upgrade(env, now=datetime(2026, 11, 19, 12, 0, 0))
    new = env.read_text()
    assert "\nSIM_AUDIO=text" not in new and "# SIM_AUDIO=text" in new
    for keep in ("DEVICE_API_TOKEN_SHA256=abc123", 'SENIOR_NAME="Frau Keller"', "AUDIO_DEVICE_NAME="):
        assert keep in new
    backup = tmp_path / ".env.vorher-20261119-120000"
    assert backup.read_text() == OLD_ENV
    assert oct(backup.stat().st_mode & 0o777) == "0o600"
    assert any("Sprechen und Tippen" in m for m in messages)


def test_variants_and_second_run_change_nothing(tmp_path):
    up = _upgrade_env()
    for line in ("SIM_AUDIO=audio", 'SIM_AUDIO="text"', "export SIM_AUDIO=TEXT", "  SIM_AUDIO = text  "):
        new, msgs = up.upgrade_text(f"A=1\n{line}\nB=2\n")
        assert len(msgs) == 1 and "\nSIM_AUDIO" not in new.replace("# SIM_AUDIO", ""), line
    for keep in ("SIM_AUDIO=auto\n", "# SIM_AUDIO=text\n", "X=SIM_AUDIO=text\n"):
        assert up.upgrade_text(keep) == (keep, [])
    env = tmp_path / ".env"
    env.write_text(OLD_ENV)
    up.upgrade(env)
    assert up.upgrade(env) == []
    assert len(list(tmp_path.glob(".env.vorher-*"))) == 1


def test_shell_reads_upgraded_env_as_auto(tmp_path):
    """What start-simulation.sh does: source .env, then config reads SIM_AUDIO."""
    up = _upgrade_env()
    env = tmp_path / ".env"
    env.write_text(OLD_ENV)
    up.upgrade(env)
    out = subprocess.run(["bash", "-c", f"set -a; . '{env}'; set +a; echo \"[${{SIM_AUDIO:-}}]\""],
                         capture_output=True, text=True, env={"PATH": os.environ["PATH"]})
    assert out.stdout.strip() == "[]"          # config default: auto


def test_prepare_script_upgrades_and_skips_setup_when_token_is_there(tmp_path):
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    for name in ("vorbereiten.sh", "upgrade_env.py"):
        (root / "scripts" / name).write_bytes((ROOT / "scripts" / name).read_bytes())
    (root / "scripts" / "demo-personen.sh").write_text("#!/bin/sh\n[ -z \"$1\" ] && echo DEMO-PERSONEN\nexit 0\n")
    os.chmod(root / "scripts" / "demo-personen.sh", 0o755)
    (root / ".env").write_text(OLD_ENV)
    run = lambda: subprocess.run(["bash", str(root / "scripts" / "vorbereiten.sh")], capture_output=True,
                                 text=True, env={"PATH": os.environ["PATH"], "PYTHON": "python3"})
    out = run()
    assert out.returncode == 0, out.stderr
    assert "SIM_AUDIO=text" in out.stdout and "DEMO-PERSONEN" not in out.stdout
    assert run().stdout == ""                  # nothing to do the second time
    (root / ".env").write_text("SIM_AUDIO=auto\n# DEVICE_API_TOKEN_SHA256=\n")
    assert "DEMO-PERSONEN" in run().stdout     # first setup: people and token
