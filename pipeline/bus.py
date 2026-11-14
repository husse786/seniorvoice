"""Message channel between the core process and the dialog process.

JSON lines over a Unix socket pair. The core creates the pair, keeps one end
and passes the other end's file descriptor to the dialog child process
(environment variable SV_BUS_FD).

Only control messages travel over the bus (call start/end, state, ping).
Conversation content never does.
"""

import json
import os
import socket
import threading
from typing import Callable

BUS_FD_ENV = "SV_BUS_FD"


class Bus:
    """Line-based JSON messages over a connected socket. Thread-safe send."""

    def __init__(self, sock: socket.socket):
        self._sock = sock
        self._file = sock.makefile("r", encoding="utf-8", newline="\n")
        self._send_lock = threading.Lock()

    @classmethod
    def from_env(cls) -> "Bus":
        fd = int(os.environ[BUS_FD_ENV])
        return cls(socket.socket(fileno=fd))

    def send(self, msg_type: str, **fields) -> bool:
        """Send one message. Returns False if the other side is gone."""
        line = json.dumps({"type": msg_type, **fields}) + "\n"
        try:
            with self._send_lock:
                self._sock.sendall(line.encode("utf-8"))
            return True
        except OSError:
            return False

    def receive(self) -> dict | None:
        """Block until the next message. Returns None when the channel closed."""
        try:
            line = self._file.readline()
        except (OSError, ValueError):
            return None
        if not line:
            return None
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return {"type": "invalid"}

    def listen(self, handler: Callable[[dict], None], name: str = "bus") -> threading.Thread:
        """Call handler for each message in a background thread until closed."""
        def run():
            while True:
                msg = self.receive()
                if msg is None:
                    handler({"type": "closed"})
                    return
                handler(msg)
        thread = threading.Thread(target=run, name=name, daemon=True)
        thread.start()
        return thread

    def close(self) -> None:
        try:
            self._sock.close()
        except OSError:
            pass
