"""Stand-in for dialog_service.py in core tests. Mode from FAKE_DIALOG_MODE:
normal (answers pings), silent (never answers), llm_hang (reports
"thinking" and stays there, still answering pings), crash (exits)."""

import os
import sys
import time

sys.path.insert(0, os.environ["PIPELINE_DIR"])
from bus import Bus  # noqa: E402

mode = os.environ.get("FAKE_DIALOG_MODE", "normal")
bus = Bus.from_env()
log_path = os.environ.get("FAKE_DIALOG_LOG")


def record(msg):
    if log_path:
        with open(log_path, "a") as fh:
            fh.write(msg.get("type", "") + "\n")


if mode == "crash":
    sys.exit(3)

bus.send("state", state="ready")
if mode == "llm_hang":
    bus.send("state", state="thinking")

while True:
    msg = bus.receive()
    if msg is None:
        break
    record(msg)
    if msg["type"] == "ping" and mode != "silent":
        bus.send("pong")
