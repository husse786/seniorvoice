"""F4 (decided 19.11.2026): Help and Family by e-mail. "Ich kümmere mich" is a
reply to the Help mail; the device reads only sender and subject (IMAP)."""

import email
from datetime import datetime, timedelta, timezone

import pytest


class FakeMailServer:
    """Stands in for SMTP and IMAP: what is sent and what is in the inbox."""

    def __init__(self):
        self.sent = []            # EmailMessage objects
        self.inbox = []           # [{"raw": bytes, "seen": bool}]
        self.starttls = 0
        self.logins = 0
        self.imap_sessions = 0
        self.fetch_parts = []

    def reply(self, sender, subject, body="Ich kümmere mich"):
        raw = (f"From: {sender}\r\nSubject: {subject}\r\n\r\n{body}\r\n").encode("utf-8")
        self.inbox.append({"raw": raw, "seen": False})


@pytest.fixture
def mail(env, monkeypatch):
    channels = env.load("channels")
    server = FakeMailServer()

    class SMTP:
        def __init__(self, host, port, timeout=None, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self, context=None):
            server.starttls += 1

        def login(self, user, password):
            server.logins += 1

        def send_message(self, msg):
            server.sent.append(msg)

    class IMAP:
        def __init__(self, host, port, timeout=None, ssl_context=None):
            server.imap_sessions += 1

        def login(self, user, password):
            pass

        def select(self, box):
            return "OK", [b"1"]

        def search(self, charset, criterion):
            nums = [str(i + 1).encode() for i, m in enumerate(server.inbox) if not m["seen"]]
            return "OK", [b" ".join(nums)]

        def fetch(self, num, parts):
            server.fetch_parts.append(parts)
            msg = email.message_from_bytes(server.inbox[int(num) - 1]["raw"])
            head = f"From: {msg['From']}\r\nSubject: {msg['Subject']}\r\n\r\n".encode()
            return "OK", [(b"1 (BODY[HEADER.FIELDS (FROM SUBJECT)] {n}", head), b")"]

        def store(self, num, op, flag):
            server.inbox[int(num) - 1]["seen"] = True

        def logout(self):
            pass

    monkeypatch.setattr(channels.smtplib, "SMTP", SMTP)
    monkeypatch.setattr(channels.smtplib, "SMTP_SSL", SMTP)
    monkeypatch.setattr(channels.imaplib, "IMAP4_SSL", IMAP)
    monkeypatch.setattr(channels.imaplib, "IMAP4", IMAP)
    clock = {"t": 1000.0}
    channel = channels.EmailChannel("mail.example.ch", "mail.example.ch", "geraet@example.ch",
                                    "secret", senior_name="Frau Keller",
                                    monotonic=lambda: clock["t"])
    return channels, channel, server, clock


def _tag(subject):
    return subject[subject.index("[SV-"):]


def test_alert_mail_uses_tls_and_carries_code(mail):
    channels, channel, server, clock = mail
    channel.send_alert("Sandra@Example.ch", "Frau Keller hat den Hilfe-Knopf gedrückt.", 7)
    msg = server.sent[0]
    assert server.starttls == 1 and server.logins == 1
    assert msg["To"] == "Sandra@Example.ch"
    assert channels.EmailChannel.TAG.search(msg["Subject"]).group(1) == "7"
    assert "antworten Sie auf diese E-Mail" in msg.get_content()


def test_reply_from_contact_is_acknowledgement(mail):
    channels, channel, server, clock = mail
    channel.send_alert("sandra@example.ch", "Hilfe", 7)
    server.reply("Sandra Keller <Sandra@Example.ch>", "Re: " + server.sent[0]["Subject"])
    assert channel.poll_acks() == [(7, "sandra@example.ch")]
    # Only sender and subject are fetched, never the reply text
    assert all("HEADER.FIELDS (FROM SUBJECT)" in p and "PEEK" in p for p in server.fetch_parts)
    assert server.inbox[0]["seen"]


def test_guessed_or_old_code_is_ignored(mail):
    channels, channel, server, clock = mail
    channel.send_alert("sandra@example.ch", "Hilfe", 7)
    server.reply("sandra@example.ch", "Re: Hilfe [SV-7-00000000]")      # wrong code
    server.reply("sandra@example.ch", "Re: Hilfe [SV-8-" + _tag(server.sent[0]["Subject"])[-9:])
    assert channel.poll_acks() == []


def test_no_mailbox_traffic_without_open_alert_and_rate_limited(mail):
    channels, channel, server, clock = mail
    assert channel.poll_acks() == [] and server.imap_sessions == 0
    channel.send_alert("sandra@example.ch", "Hilfe", 7)
    channel.poll_acks()
    channel.poll_acks()                                  # within 15 s: no second login
    assert server.imap_sessions == 1
    clock["t"] += 16
    channel.poll_acks()
    assert server.imap_sessions == 2
    clock["t"] += channels.EmailChannel.KEEP_SECONDS + 1
    channel.poll_acks()                                  # code forgotten: no traffic
    assert server.imap_sessions == 2


def test_family_message(mail):
    channels, channel, server, clock = mail
    channel.send_message("sandra@example.ch", "Ich denke an dich.")
    msg = server.sent[0]
    assert msg["Subject"] == "Nachricht von Frau Keller"
    assert msg.get_content().strip() == "Ich denke an dich."


def test_channel_from_env(env):
    env.set(CHANNEL="email", MAIL_SMTP_HOST="mail.example.ch", MAIL_IMAP_HOST="mail.example.ch",
            MAIL_USER="geraet@example.ch", MAIL_PASSWORD="x")
    channels = env.load("channels")
    assert isinstance(channels.channel_from_env(), channels.EmailChannel)
    env.set(MAIL_PASSWORD="")
    channels = env.load("channels")
    with pytest.raises(ValueError):
        channels.channel_from_env()


def test_help_service_closes_alert_on_email_reply(mail, env):
    channels, channel, server, clock = mail
    help_mod = __import__("help_alert")
    help_mod.set_contacts([{"name": "Sandra", "role": "Tochter", "address": "sandra@example.ch"}])
    wall = {"t": datetime(2026, 11, 20, 13, 0, tzinfo=timezone.utc)}
    said = []
    service = help_mod.HelpService(channel, announce=said.append, senior_name="Frau Keller",
                                   now=lambda: wall["t"], monotonic=lambda: clock["t"])
    service.trigger()
    service.step()
    assert server.sent == []                      # waits: a second press may cancel
    clock["t"] += help_mod.CANCEL_SECONDS
    service.step()
    assert len(server.sent) == 1
    server.reply("SANDRA@example.ch", "Re: " + server.sent[0]["Subject"])
    clock["t"] += 20
    wall["t"] += timedelta(seconds=20)
    service.step()
    assert said[-1] == "Sandra hat geantwortet und kümmert sich um Sie."
    assert help_mod.list_alerts()[0]["status"] == "quittiert"
