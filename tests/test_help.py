"""Decisions A3, A13, A14, A15: Help notifies contacts in order, escalates, then says 144."""

import json
from datetime import datetime, timedelta, timezone

import pytest


class Clock:
    def __init__(self):
        self.wall = datetime(2026, 11, 20, 13, 0, tzinfo=timezone.utc)
        self.mono = 0.0

    def advance(self, seconds):
        self.wall += timedelta(seconds=seconds)
        self.mono += seconds


@pytest.fixture
def help_env(env):
    help_mod = env.load("help_alert")
    channels = __import__("channels")
    help_mod.set_contacts([
        {"name": "Sandra", "role": "Tochter", "address": "chat-sandra"},
        {"name": "Spitex Winterthur", "role": "Spitex", "address": "chat-spitex"},
    ])
    channel = channels.ConsoleChannel()
    clock = Clock()
    said = []
    service = help_mod.HelpService(channel, announce=said.append, senior_name="Frau Keller",
                                   now=lambda: clock.wall, monotonic=lambda: clock.mono)
    return help_mod, service, channel, clock, said


def test_help_notifies_first_contact_and_confirms(help_env):
    help_mod, service, channel, clock, said = help_env
    service.trigger()
    assert said == ["Ich informiere jetzt Sandra. Im Notfall rufen Sie bitte 144 an."]
    service.step()
    address, text, alert_id = channel.sent[0]
    assert address == "chat-sandra"
    assert "Frau Keller" in text and "Hilfe-Knopf" in text and "kein Notruf" in text


def test_acknowledgement_closes_alert(help_env):
    help_mod, service, channel, clock, said = help_env
    service.trigger()
    service.step()
    alert_id = channel.sent[0][2]
    channel.simulate_ack(alert_id, "chat-sandra")
    clock.advance(30)
    service.step()
    assert said[-1] == "Sandra hat geantwortet und kümmert sich um Sie."
    alert = help_mod.list_alerts()[0]
    assert alert["status"] == "quittiert" and alert["acknowledged_by"] == "Sandra"


def test_escalates_after_10_minutes_then_says_144(help_env):
    help_mod, service, channel, clock, said = help_env
    service.trigger()
    service.step()
    clock.advance(9 * 60)
    service.step()
    assert len(channel.sent) == 1                       # not before 10 min
    clock.advance(60)
    service.step()                                      # escalate
    service.step()                                      # send to next
    assert [s[0] for s in channel.sent] == ["chat-sandra", "chat-spitex"]
    assert "Ich informiere jetzt Spitex Winterthur" in said[-1]
    clock.advance(10 * 60)
    service.step()
    assert said[-1] == "Ich konnte niemanden erreichen. Bitte rufen Sie 144 an."
    assert help_mod.list_alerts()[0]["status"] == "niemand erreicht"


def test_ack_from_unknown_sender_is_ignored(help_env):
    help_mod, service, channel, clock, said = help_env
    service.trigger()
    service.step()
    channel.simulate_ack(channel.sent[0][2], "chat-stranger")
    service.step()
    assert help_mod.list_alerts()[0]["status"] == "offen"


def test_no_network_says_144_quickly(help_env, monkeypatch):
    help_mod, service, channel, clock, said = help_env

    def broken(*a):
        raise OSError("no network")
    monkeypatch.setattr(channel, "send_alert", broken)
    service.trigger()
    service.step()
    clock.advance(61)
    service.step()
    assert said[-1] == "Ich konnte niemanden erreichen. Bitte rufen Sie 144 an."


def test_second_press_does_not_spam(help_env):
    help_mod, service, channel, clock, said = help_env
    service.trigger()
    service.step()
    service.trigger()
    assert said[-1].startswith("Ich habe Sandra bereits informiert")
    assert len(help_mod.list_alerts()) == 1


def test_no_contacts_says_144(help_env):
    help_mod, service, channel, clock, said = help_env
    help_mod.set_contacts([])
    service.trigger()
    assert said == [help_mod.SAY_NO_CONTACTS]


def test_alerts_deleted_after_30_days(help_env):
    help_mod, service, channel, clock, said = help_env
    service.trigger()
    assert help_mod.purge_expired(clock.wall + timedelta(days=29)) == 0
    assert help_mod.purge_expired(clock.wall + timedelta(days=31)) == 1


def test_telegram_message_has_ack_button_and_parses_press(env, monkeypatch):
    channels = env.load("channels")
    calls = []

    def fake_call(self, method, **params):
        calls.append((method, params))
        if method == "getUpdates":
            return [{"update_id": 7, "callback_query": {
                "id": "q1", "data": "ack:12", "message": {"chat": {"id": 555}}}}]
        return {}
    monkeypatch.setattr(channels.TelegramChannel, "_call", fake_call)
    tg = channels.TelegramChannel("token")
    tg.send_alert("555", "Hilfe", 12)
    method, params = calls[0]
    assert method == "sendMessage"
    assert params["reply_markup"]["inline_keyboard"][0][0] == {
        "text": "Ich kümmere mich", "callback_data": "ack:12"}
    assert tg.poll_acks() == [(12, "555")]
    assert tg._offset == 8
    assert calls[-1][0] == "answerCallbackQuery"


def test_help_works_while_dialog_hangs_with_real_service(env, monkeypatch):
    """Core + HelpService: Help button answered immediately, no dialog involved."""
    core_mod = env.load("core_service")
    help_mod = __import__("help_alert")
    channels = __import__("channels")
    hw = __import__("hardware")
    help_mod.set_contacts([{"name": "Sandra", "role": "Tochter", "address": "x"}])
    said = []

    class DeadSupervisor:
        on_restart = None

        def send(self, *a, **k):
            raise AssertionError("Help must not go through the dialog")

        def check(self):
            pass
    service = help_mod.HelpService(channels.ConsoleChannel(), announce=said.append)
    core = core_mod.Core(DeadSupervisor(), hw.SimulatedRinger(), help_handler=service,
                         announce=said.append, with_reminders=False)
    core.handle(hw.InputEvent("button", "hilfe"))
    assert said == ["Ich informiere jetzt Sandra. Im Notfall rufen Sie bitte 144 an."]
