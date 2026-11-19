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
    service.step()                                      # worker started: knows the first contact
    return help_mod, service, channel, clock, said


def press_and_send(help_mod, service, clock):
    """Press Help and let the cancel window pass, so the notice goes out."""
    service.trigger()
    service.step()
    clock.advance(help_mod.CANCEL_SECONDS)
    service.step()


def test_help_notifies_first_contact_and_confirms(help_env):
    help_mod, service, channel, clock, said = help_env
    service.trigger()
    # Said by the press itself (core thread: a queue, no DB, no network)
    assert said == ["Ich informiere gleich Sandra. Im Notfall rufen Sie bitte 144 an. "
                    "Falls das ein Versehen war, drücken Sie nochmals Hilfe."]
    service.step()
    assert len(said) == 1
    assert channel.sent == []                           # waits for a possible cancel
    clock.advance(9)
    service.step()
    assert channel.sent == []
    clock.advance(1)
    service.step()
    assert said[-1] == "Ich habe Sandra informiert. Im Notfall rufen Sie bitte 144 an."
    address, text, alert_id = channel.sent[0]
    assert address == "chat-sandra"
    assert "Frau Keller" in text and "Hilfe-Knopf" in text and "kein Notruf" in text


def test_acknowledgement_closes_alert(help_env):
    help_mod, service, channel, clock, said = help_env
    press_and_send(help_mod, service, clock)
    alert_id = channel.sent[0][2]
    channel.simulate_ack(alert_id, "chat-sandra")
    clock.advance(30)
    service.step()
    assert said[-1] == "Sandra hat geantwortet und kümmert sich um Sie."
    alert = help_mod.list_alerts()[0]
    assert alert["status"] == "quittiert" and alert["acknowledged_by"] == "Sandra"


def test_escalates_after_10_minutes_then_says_144(help_env):
    help_mod, service, channel, clock, said = help_env
    press_and_send(help_mod, service, clock)
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
    press_and_send(help_mod, service, clock)
    channel.simulate_ack(channel.sent[0][2], "chat-stranger")
    service.step()
    assert help_mod.list_alerts()[0]["status"] == "offen"


def test_no_network_says_144_quickly(help_env, monkeypatch):
    help_mod, service, channel, clock, said = help_env

    def broken(*a):
        raise OSError("no network")
    monkeypatch.setattr(channel, "send_alert", broken)
    press_and_send(help_mod, service, clock)          # 60 s count from the end of the wait
    clock.advance(59)
    service.step()
    assert help_mod.list_alerts()[0]["status"] == "offen"
    clock.advance(2)
    service.step()
    assert said[-1] == "Ich konnte niemanden erreichen. Bitte rufen Sie 144 an."


def test_second_press_does_not_spam(help_env):
    help_mod, service, channel, clock, said = help_env
    press_and_send(help_mod, service, clock)
    service.trigger()
    assert said[-1].startswith("Ich habe Sandra bereits informiert")
    assert len(help_mod.list_alerts()) == 1


def test_no_contacts_says_144(help_env):
    help_mod, service, channel, clock, said = help_env
    help_mod.set_contacts([])
    clock.advance(10)
    service.step()                                      # name cache refreshed
    service.trigger()
    service.step()
    assert said == [help_mod.SAY_NO_CONTACTS]


def test_alerts_deleted_after_30_days(help_env):
    help_mod, service, channel, clock, said = help_env
    service.trigger()
    service.step()
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
    service.run_worker(interval=5.0)
    try:
        import time
        t = time.monotonic()
        core.handle(hw.InputEvent("button", "hilfe"))
        assert time.monotonic() - t < 0.1           # core thread returns at once
        for _ in range(100):
            if said:
                break
            time.sleep(0.01)
        assert said and said[0].startswith("Ich informiere gleich")
    finally:
        service.stop()


def test_escalation_gives_next_contact_its_own_delivery_deadline(help_env, monkeypatch):
    help_mod, service, channel, clock, said = help_env
    press_and_send(help_mod, service, clock)                                      # delivered to Sandra
    real = channel.send_alert

    def spitex_unreachable(address, text, alert_id):
        if address == "chat-spitex":
            raise OSError("no route")
        return real(address, text, alert_id)
    monkeypatch.setattr(channel, "send_alert", spitex_unreachable)
    clock.advance(10 * 60)
    service.step()                                      # escalate, delivery fails
    clock.advance(30)
    service.step()
    assert help_mod.list_alerts()[0]["status"] == "offen"
    clock.advance(31)
    service.step()
    assert said[-1] == help_mod.SAY_CALL_144
    assert help_mod.list_alerts()[0]["status"] == "niemand erreicht"


def test_editing_contacts_during_alert_does_not_break_it(help_env):
    help_mod, service, channel, clock, said = help_env
    press_and_send(help_mod, service, clock)
    help_mod.set_contacts([])                           # list replaced during the alert
    service.trigger()                                   # second press
    assert said[-1].startswith("Ich habe Sandra bereits informiert")
    service.simulate_ack()
    service.step()
    assert said[-1] == "Sandra hat geantwortet und kümmert sich um Sie."


def test_open_alert_after_restart_is_closed_with_144(help_env):
    help_mod, service, channel, clock, said = help_env
    press_and_send(help_mod, service, clock)            # alert open, then the core restarts
    restarted = help_mod.HelpService(channel, announce=said.append,
                                     now=lambda: clock.wall, monotonic=lambda: clock.mono)
    clock.advance(120)
    restarted.step()
    assert said[-1] == help_mod.SAY_CALL_144
    assert help_mod.list_alerts()[0]["status"] == "niemand erreicht"
    restarted.trigger()
    restarted.step()                                    # a new press works normally
    assert said[-1].startswith("Ich informiere gleich Sandra")


def test_database_failure_still_says_144(help_env, monkeypatch):
    help_mod, service, channel, clock, said = help_env

    def locked():
        raise help_mod.sqlite3.OperationalError("database is locked")
    service.step()                                      # startup recovery done
    monkeypatch.setattr(help_mod, "_conn", locked)
    service.trigger()
    service.step()
    assert said[-1] == help_mod.SAY_CALL_144


# --- Cancel (Husey 19.11.2026): second press within 10 s, before sending ---

def test_second_press_within_window_cancels_and_nobody_is_told(help_env):
    help_mod, service, channel, clock, said = help_env
    service.trigger()
    service.step()
    clock.advance(5)
    service.trigger()                                   # second press
    service.step()
    assert said[-1] == help_mod.SAY_CANCELLED
    clock.advance(60)
    service.step()
    assert channel.sent == []                           # no notice, so no all-clear needed
    alert = help_mod.list_alerts()[0]
    assert alert["status"] == "abgebrochen" and not alert["delivered"]


def test_quick_panic_presses_do_not_cancel(help_env):
    """Presses less than 2 s apart are ignored."""
    help_mod, service, channel, clock, said = help_env
    service.trigger()
    service.trigger()                                   # before the worker even ran
    service.step()
    clock.advance(1)
    service.trigger()
    service.trigger()
    service.step()
    assert help_mod.SAY_CANCELLED not in said
    clock.advance(9)
    service.step()
    assert [s[0] for s in channel.sent] == ["chat-sandra"]
    assert help_mod.list_alerts()[0]["status"] == "offen"


def test_press_after_window_does_not_cancel(help_env):
    help_mod, service, channel, clock, said = help_env
    press_and_send(help_mod, service, clock)
    clock.advance(1)
    service.trigger()
    service.step()
    assert said[-1].startswith("Ich habe Sandra bereits informiert")
    assert help_mod.list_alerts()[0]["status"] == "offen"


def test_press_at_window_end_does_not_race_the_send(help_env):
    help_mod, service, channel, clock, said = help_env
    service.trigger()
    service.step()
    clock.advance(help_mod.CANCEL_SECONDS)
    service.trigger()                                   # exactly at the end: too late
    service.step()
    assert len(channel.sent) == 1
    assert help_mod.list_alerts()[0]["status"] == "offen"


def test_after_a_cancel_next_press_goes_out_at_once(help_env):
    help_mod, service, channel, clock, said = help_env
    service.trigger()
    service.step()
    clock.advance(3)
    service.trigger()
    service.step()                                      # cancelled
    clock.advance(4)
    service.trigger()                                   # needs help after all
    service.step()
    assert said[-1] == "Ich informiere jetzt Sandra. Im Notfall rufen Sie bitte 144 an."
    assert [s[0] for s in channel.sent] == ["chat-sandra"]
    clock.advance(3)
    service.trigger()                                   # cannot be cancelled now
    service.step()
    assert said[-1].startswith("Ich habe Sandra bereits informiert")
    assert [a["status"] for a in help_mod.list_alerts()] == ["abgebrochen", "offen"]


def test_cancel_window_returns_two_minutes_after_a_cancel(help_env):
    help_mod, service, channel, clock, said = help_env
    service.trigger()
    service.step()
    clock.advance(3)
    service.trigger()
    service.step()
    clock.advance(help_mod.NO_CANCEL_AFTER_CANCEL_SECONDS)
    service.trigger()
    service.step()
    assert said[-1] == help_mod.SAY_HOLD.format(name="Sandra")
    assert channel.sent == []


def test_cancelled_alert_never_comes_back_after_restart(help_env):
    help_mod, service, channel, clock, said = help_env
    service.trigger()
    service.step()
    clock.advance(3)
    service.trigger()
    service.step()
    restarted = help_mod.HelpService(channel, announce=said.append,
                                     now=lambda: clock.wall, monotonic=lambda: clock.mono)
    count = len(said)
    restarted.step()
    assert len(said) == count                           # no 144, nothing sent
    assert channel.sent == [] and help_mod.list_alerts()[0]["status"] == "abgebrochen"


def test_restart_during_wait_says_144(help_env):
    """Not sent yet when the device restarts: be safe and say 144 (A14)."""
    help_mod, service, channel, clock, said = help_env
    service.trigger()
    service.step()
    restarted = help_mod.HelpService(channel, announce=said.append,
                                     now=lambda: clock.wall, monotonic=lambda: clock.mono)
    clock.advance(30)
    restarted.step()
    assert said[-1] == help_mod.SAY_CALL_144
    assert help_mod.list_alerts()[0]["status"] == "niemand erreicht"


def test_no_acknowledgement_possible_while_waiting(help_env):
    help_mod, service, channel, clock, said = help_env
    service.trigger()
    service.step()
    service.simulate_ack()                              # sim button: nothing was sent yet
    clock.advance(help_mod.CANCEL_SECONDS)
    service.step()
    assert help_mod.list_alerts()[0]["status"] == "offen"


def test_screen_and_phone_show_the_phases(help_env):
    help_mod, service, channel, clock, said = help_env
    assert service.phase() is None
    service.trigger()
    assert service.phase() == "wartet"
    service.step()
    clock.advance(3)
    status = service.screen_status()
    assert status["phase"] == "wartet" and status["rest"] == 7 and status["kontakt"] == "Sandra"
    service.trigger()
    service.step()
    assert service.phase() == "abgebrochen" and not service.is_open()
    clock.advance(help_mod.CANCELLED_SHOWN_SECONDS)
    assert service.phase() is None
    clock.advance(help_mod.NO_CANCEL_AFTER_CANCEL_SECONDS)
    press_and_send(help_mod, service, clock)
    assert service.phase() == "unterwegs"


def test_worker_sends_on_time_without_a_further_press(env):
    """Real worker thread: the notice goes out about CANCEL_SECONDS after the press."""
    import time
    help_mod = env.load("help_alert")
    channels = __import__("channels")
    help_mod.set_contacts([{"name": "Sandra", "role": "Tochter", "address": "x"}])
    channel = channels.ConsoleChannel()
    service = help_mod.HelpService(channel, announce=lambda t: None)
    original = help_mod.CANCEL_SECONDS
    help_mod.CANCEL_SECONDS = 0.3
    try:
        service.run_worker(interval=5.0)
        service.trigger()
        deadline = time.monotonic() + 3
        while not channel.sent and time.monotonic() < deadline:
            time.sleep(0.02)
        assert channel.sent                              # did not wait for the 5 s interval
    finally:
        help_mod.CANCEL_SECONDS = original
        service.stop()


def test_press_while_alert_is_being_created_cancels_it(help_env, monkeypatch):
    """Review PR #17: the database is slow (locked by the portal) while the
    alert is created, and the second press comes in during that time."""
    help_mod, service, channel, clock, said = help_env
    real = help_mod.get_contacts

    def slow_contacts():
        clock.advance(3)
        service.trigger()                               # second press, 3 s after the first
        return real()
    monkeypatch.setattr(help_mod, "get_contacts", slow_contacts)
    service.trigger()
    service.step()
    assert said[-1] == help_mod.SAY_CANCELLED
    clock.advance(30)
    service.step()
    assert channel.sent == []
    assert [a["status"] for a in help_mod.list_alerts()] == ["abgebrochen"]


def test_double_press_while_alert_is_being_created_makes_one_alert(help_env, monkeypatch):
    help_mod, service, channel, clock, said = help_env
    real = help_mod.get_contacts

    def slow_contacts():
        clock.advance(0.3)
        service.trigger()                               # bounce / double tap: ignored
        return real()
    monkeypatch.setattr(help_mod, "get_contacts", slow_contacts)
    service.trigger()
    service.step()
    clock.advance(help_mod.CANCEL_SECONDS)
    service.step()
    assert len(channel.sent) == 1
    assert [a["status"] for a in help_mod.list_alerts()] == ["offen"]


def test_panic_burst_running_past_two_seconds_does_not_cancel(help_env):
    help_mod, service, channel, clock, said = help_env
    for _ in range(8):                                  # pressing every 0.7 s for 5 s
        service.trigger()
        service.step()
        clock.advance(0.7)
    assert help_mod.SAY_CANCELLED not in said
    clock.advance(help_mod.CANCEL_SECONDS)
    service.step()
    assert [s[0] for s in channel.sent] == ["chat-sandra"]


def test_quick_press_after_cancel_does_not_toggle(help_env):
    help_mod, service, channel, clock, said = help_env
    service.trigger()
    service.step()
    clock.advance(3)
    service.trigger()
    service.step()                                      # cancelled
    clock.advance(0.3)
    service.trigger()                                   # double tap on cancel: ignored
    service.step()
    assert said[-1] == help_mod.SAY_CANCELLED and channel.sent == []
    clock.advance(3)
    service.trigger()                                   # deliberate press: goes out at once
    service.step()
    assert [s[0] for s in channel.sent] == ["chat-sandra"]


def test_late_worker_sends_when_it_gets_there(help_env):
    """Worker busy (e.g. mail poll) for 11 s: the prompt was heard at the press,
    the 10 s are over, so it sends at once."""
    help_mod, service, channel, clock, said = help_env
    service.trigger()
    clock.advance(11)
    service.trigger()                                   # too late to cancel: told so
    assert said[-1] == help_mod.SAY_SENDING.format(name="Sandra")
    service.step()
    assert [s[0] for s in channel.sent] == ["chat-sandra"]
    assert said[-1] == "Ich habe Sandra informiert. Im Notfall rufen Sie bitte 144 an."


def test_countdown_while_request_waits_for_worker(help_env):
    help_mod, service, channel, clock, said = help_env
    service.trigger()
    clock.advance(4)
    assert service.screen_status()["rest"] == 6


def test_cancel_before_worker_starts(help_env):
    """Worker late (mail poll): prompt at the press, cancel 5 s later, worker at 12 s."""
    help_mod, service, channel, clock, said = help_env
    service.trigger()
    clock.advance(5)
    service.trigger()
    clock.advance(7)
    service.step()
    assert said == [help_mod.SAY_HOLD.format(name="Sandra"), help_mod.SAY_CANCELLED]
    clock.advance(30)
    service.step()
    assert channel.sent == []
    assert [a["status"] for a in help_mod.list_alerts()] == ["abgebrochen"]


def test_press_while_cancel_pending_becomes_new_request(help_env):
    """Third review: Help, cancel, Help again before the worker ran."""
    help_mod, service, channel, clock, said = help_env
    service.trigger()
    clock.advance(3)
    service.trigger()                                   # cancel (pending)
    clock.advance(3)
    service.trigger()                                   # needs help after all
    service.step()
    service.step()
    assert said[-2:] == [help_mod.SAY_CANCELLED,
                         "Ich informiere jetzt Sandra. Im Notfall rufen Sie bitte 144 an."]
    assert [s[0] for s in channel.sent] == ["chat-sandra"]
    assert [a["status"] for a in help_mod.list_alerts()] == ["abgebrochen", "offen"]


def test_cancel_with_database_error_says_cancelled_not_144(help_env, monkeypatch):
    help_mod, service, channel, clock, said = help_env
    service.trigger()
    clock.advance(3)
    service.trigger()

    def locked():
        raise help_mod.sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(help_mod, "get_contacts", locked)
    service.step()
    assert said[-1] == help_mod.SAY_CANCELLED and help_mod.SAY_CALL_144 not in said


def test_cancel_with_no_contacts_is_stored_as_cancelled(help_env):
    help_mod, service, channel, clock, said = help_env
    service.trigger()
    help_mod.set_contacts([])
    clock.advance(3)
    service.trigger()
    service.step()
    assert said[-1] == help_mod.SAY_CANCELLED
    assert [a["status"] for a in help_mod.list_alerts()] == ["abgebrochen"]


def test_press_right_at_window_end_gets_feedback(help_env):
    help_mod, service, channel, clock, said = help_env
    service.trigger()
    service.step()
    clock.advance(help_mod.CANCEL_SECONDS)
    service.trigger()                                   # before the worker flips "held"
    assert said[-1] == help_mod.SAY_SENDING.format(name="Sandra")


def test_panic_pressing_after_cancel_still_gets_help(help_env):
    help_mod, service, channel, clock, said = help_env
    service.trigger()
    service.step()
    clock.advance(3)
    service.trigger()
    service.step()                                      # cancelled
    for _ in range(4):                                  # then presses every second
        clock.advance(1)
        service.trigger()
        service.step()
    assert [s[0] for s in channel.sent] == ["chat-sandra"]
    assert [a["status"] for a in help_mod.list_alerts()] == ["abgebrochen", "offen"]


def test_press_while_sending_does_not_claim_delivery(help_env, monkeypatch):
    help_mod, service, channel, clock, said = help_env

    def failing(*a):
        raise OSError("smtp timeout")
    monkeypatch.setattr(channel, "send_alert", failing)
    press_and_send(help_mod, service, clock)            # wait over, sending fails
    clock.advance(3)
    service.trigger()
    assert said[-1] == help_mod.SAY_SENDING.format(name="Sandra")


def test_cancel_is_announced_even_if_the_database_fails(help_env, monkeypatch):
    help_mod, service, channel, clock, said = help_env
    service.trigger()
    service.step()
    clock.advance(3)
    service.trigger()

    def locked():
        raise help_mod.sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(help_mod, "_conn", locked)
    service.step()
    assert said[-1] == help_mod.SAY_CANCELLED
    assert channel.sent == [] and not service.is_open()


def test_notice_names_the_time_of_the_press(help_env):
    help_mod, service, channel, clock, said = help_env
    clock.wall = clock.wall.replace(minute=59, second=55)     # 14:59:55 Swiss time
    service.trigger()
    service.step()
    clock.advance(help_mod.CANCEL_SECONDS)                    # sent at 15:00:05
    service.step()
    assert "um 14:59 Uhr" in channel.sent[0][1]


def test_confirmation_said_even_if_history_write_fails(help_env, monkeypatch):
    help_mod, service, channel, clock, said = help_env
    service.trigger()
    service.step()
    clock.advance(help_mod.CANCEL_SECONDS)
    real = help_mod._conn

    def locked_after_send():
        if channel.sent:
            raise help_mod.sqlite3.OperationalError("database is locked")
        return real()
    monkeypatch.setattr(help_mod, "_conn", locked_after_send)
    service.step()
    assert said[-1] == "Ich habe Sandra informiert. Im Notfall rufen Sie bitte 144 an."
