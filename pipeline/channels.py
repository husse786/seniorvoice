"""Outgoing channel for Help and Family (decision A4: one channel for both).

The channel only carries what the senior chose to send (Family) or a Help
notice without any conversation content (M7). It is not the LLM: it may use
the internet. The provider must be documented in the privacy notes (A4).

- ConsoleChannel: development and tests; acknowledgements are simulated.
- TelegramChannel: Telegram Bot API. Each Help message has a button
  "Ich kümmere mich"; the device polls for the press (no open port, A14).
  Choice of channel is open question F4 (recommendation: Telegram).
"""

import json
import os
import threading
import urllib.parse
import urllib.request

from logging_config import get_logger

log = get_logger("channel")

ACK_BUTTON = "Ich kümmere mich"


class Channel:
    def send_alert(self, address: str, text: str, alert_id: int) -> None:
        raise NotImplementedError

    def send_message(self, address: str, text: str) -> None:
        raise NotImplementedError

    def poll_acks(self) -> list[tuple[int, str]]:
        """Acknowledgements since the last poll: [(alert_id, address), ...]."""
        raise NotImplementedError


class ConsoleChannel(Channel):
    """Logs instead of sending. simulate_ack() stands in for the button press."""

    def __init__(self):
        self.sent: list[tuple[str, str, int | None]] = []
        self._acks: list[tuple[int, str]] = []
        self._lock = threading.Lock()

    def send_alert(self, address, text, alert_id):
        self.sent.append((address, text, alert_id))
        log.warning("[console channel] alert %d to %s", alert_id, address)

    def send_message(self, address, text):
        self.sent.append((address, text, None))
        log.info("[console channel] message to %s (%d chars)", address, len(text))

    def simulate_ack(self, alert_id: int, address: str) -> None:
        with self._lock:
            self._acks.append((alert_id, address))

    def poll_acks(self):
        with self._lock:
            acks, self._acks = self._acks, []
        return acks


class TelegramChannel(Channel):
    """Telegram Bot API over HTTPS. address = the contact's chat id."""

    API = "https://api.telegram.org/bot{token}/{method}"

    def __init__(self, token: str, timeout: float = 10.0):
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN is not set")
        self.token = token
        self.timeout = timeout
        self._offset = 0

    def _call(self, method: str, **params):
        url = self.API.format(token=self.token, method=method)
        body = json.dumps(params).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if not data.get("ok"):
            raise RuntimeError(f"Telegram {method} failed")
        return data["result"]

    def send_alert(self, address, text, alert_id):
        self._call("sendMessage", chat_id=address, text=text, reply_markup={
            "inline_keyboard": [[{"text": ACK_BUTTON, "callback_data": f"ack:{alert_id}"}]]
        })

    def send_message(self, address, text):
        self._call("sendMessage", chat_id=address, text=text)

    def poll_acks(self):
        updates = self._call("getUpdates", offset=self._offset, timeout=0,
                             allowed_updates=["callback_query"])
        acks = []
        for upd in updates:
            self._offset = max(self._offset, upd["update_id"] + 1)
            cq = upd.get("callback_query")
            if not cq or not str(cq.get("data", "")).startswith("ack:"):
                continue
            try:
                alert_id = int(cq["data"].split(":", 1)[1])
            except ValueError:
                continue
            chat_id = str(cq.get("message", {}).get("chat", {}).get("id", ""))
            acks.append((alert_id, chat_id))
            try:
                self._call("answerCallbackQuery", callback_query_id=cq["id"],
                           text="Danke, das Gerät sagt Bescheid.")
            except Exception:
                pass
        return acks


def channel_from_env() -> Channel:
    kind = os.getenv("CHANNEL", "console").lower()
    if kind == "telegram":
        return TelegramChannel(os.getenv("TELEGRAM_BOT_TOKEN", ""))
    return ConsoleChannel()
