"""Outgoing channel for Help and Family (decision A4: one channel for both).

The channel only carries what the senior chose to send (Family) or a Help
notice without any conversation content (M7). It is not the LLM: it may use
the internet. The provider must be documented in the privacy notes (A4).

- ConsoleChannel: development and tests; acknowledgements are simulated.
- EmailChannel (decided F4, 19.11.2026): e-mail over SMTP. "Ich kümmere
  mich" = a reply to the Help mail; the device fetches only sender and
  subject of new mails over IMAP (no open port, A14). Reply bodies are never
  read. A confirmation link into the portal follows once there is a server.
- TelegramChannel: Telegram Bot API (kept, not used: F4 = e-mail).
"""

import email.utils
import imaplib
import json
import os
import re
import secrets
import smtplib
import ssl
import threading
import time
import urllib.parse
import urllib.request
from email.header import decode_header, make_header
from email.message import EmailMessage

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


class EmailChannel(Channel):
    """E-mail. address = the contact's e-mail address.

    Each Help mail carries a tag with a random code in its subject, e.g.
    "[SV-12-a1b2c3d4]". A reply keeps the subject; it counts as "Ich kümmere
    mich" only if it comes from a contact's address and carries the code of
    an alert sent in the last hours. Only sender and subject are fetched.
    """

    TAG = re.compile(r"\[SV-(\d{1,12})-([0-9a-f]{8})\]")
    KEEP_SECONDS = 3 * 3600        # codes of older alerts are forgotten
    POLL_SECONDS = 15              # IMAP at most this often, only while codes are open

    def __init__(self, smtp_host: str, imap_host: str, user: str, password: str,
                 sender: str = "", smtp_port: int = 587, imap_port: int = 993,
                 senior_name: str = "", timeout: float = 15.0,
                 monotonic=time.monotonic):
        if not (smtp_host and imap_host and user and password):
            raise ValueError("MAIL_SMTP_HOST, MAIL_IMAP_HOST, MAIL_USER, MAIL_PASSWORD needed")
        self.smtp_host, self.smtp_port = smtp_host, smtp_port
        self.imap_host, self.imap_port = imap_host, imap_port
        self.user, self.password = user, password
        self.sender = sender or user
        self.senior_name = senior_name
        self.timeout = timeout
        self.monotonic = monotonic
        self._codes: dict[int, tuple[str, float]] = {}
        self._last_poll = -1e9
        self._lock = threading.Lock()

    @staticmethod
    def _local(host: str) -> bool:
        return host in ("127.0.0.1", "localhost", "::1")

    def _send(self, to: str, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["From"] = self.sender
        msg["To"] = to
        msg["Subject"] = subject
        msg["Date"] = email.utils.formatdate(localtime=True)
        msg["Message-ID"] = email.utils.make_msgid(domain="seniorvoice.local")
        msg.set_content(body)
        context = ssl.create_default_context()
        if self.smtp_port == 465:
            server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=self.timeout,
                                      context=context)
        else:
            server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=self.timeout)
        with server:
            if self.smtp_port != 465 and not self._local(self.smtp_host):
                server.starttls(context=context)      # never plain text over the internet
            if not self._local(self.smtp_host) or self.password != "-":
                server.login(self.user, self.password)
            server.send_message(msg)

    def send_alert(self, address, text, alert_id):
        with self._lock:
            code = self._codes.get(alert_id, (secrets.token_hex(4), 0))[0]
            self._codes[alert_id] = (code, self.monotonic())
        body = (f"{text}\n\n"
                "Bitte antworten Sie auf diese E-Mail, wenn Sie sich kümmern (zum Beispiel "
                "mit «Ich kümmere mich»). Das Telefon sagt dann Bescheid. Ohne Antwort innert "
                "10 Minuten geht die Meldung an die nächste Kontaktperson.\n")
        self._send(address, f"Hilfe-Knopf gedrückt [SV-{alert_id}-{code}]", body)

    def send_message(self, address, text):
        who = self.senior_name or "SeniorVoice"
        self._send(address, f"Nachricht von {who}", text + "\n")

    def _open_codes(self) -> dict[int, str]:
        now = self.monotonic()
        with self._lock:
            for alert_id in [a for a, (_, t) in self._codes.items() if now - t > self.KEEP_SECONDS]:
                del self._codes[alert_id]
            return {a: c for a, (c, _) in self._codes.items()}

    def poll_acks(self):
        codes = self._open_codes()
        if not codes or self.monotonic() - self._last_poll < self.POLL_SECONDS:
            return []           # no mailbox traffic while no Help mail is open
        self._last_poll = self.monotonic()
        if self._local(self.imap_host) and self.imap_port != 993:
            box = imaplib.IMAP4(self.imap_host, self.imap_port, timeout=self.timeout)
        else:
            box = imaplib.IMAP4_SSL(self.imap_host, self.imap_port, timeout=self.timeout,
                                    ssl_context=ssl.create_default_context())
        acks = []
        try:
            box.login(self.user, self.password)
            box.select("INBOX")
            status, data = box.search(None, "UNSEEN")
            for num in (data[0].split() if status == "OK" and data and data[0] else []):
                status, parts = box.fetch(num, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
                raw = b"".join(p[1] for p in parts if isinstance(p, tuple)) if status == "OK" else b""
                headers = email.message_from_bytes(raw)
                sender = email.utils.parseaddr(str(headers.get("From", "")))[1].lower()
                subject = str(make_header(decode_header(str(headers.get("Subject", "")))))
                match = self.TAG.search(subject)
                if match and codes.get(int(match.group(1))) == match.group(2) and sender:
                    acks.append((int(match.group(1)), sender))
                box.store(num, "+FLAGS", "\\Seen")
        finally:
            try:
                box.logout()
            except Exception:
                pass
        return acks


def channel_from_env() -> Channel:
    kind = os.getenv("CHANNEL", "console").lower()
    if kind == "email":
        return EmailChannel(
            os.getenv("MAIL_SMTP_HOST", ""), os.getenv("MAIL_IMAP_HOST", ""),
            os.getenv("MAIL_USER", ""), os.getenv("MAIL_PASSWORD", ""),
            sender=os.getenv("MAIL_FROM", ""),
            smtp_port=int(os.getenv("MAIL_SMTP_PORT", "587")),
            imap_port=int(os.getenv("MAIL_IMAP_PORT", "993")),
            senior_name=os.getenv("SENIOR_NAME", ""))
    if kind == "telegram":
        return TelegramChannel(os.getenv("TELEGRAM_BOT_TOKEN", ""))
    return ConsoleChannel()
