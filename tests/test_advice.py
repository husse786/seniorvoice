"""Rat button (PR 9, B2): answers only from entered information."""

import json
import logging
import socket
import sys
import types
from pathlib import Path

import pytest

QUESTIONS = json.loads((Path(__file__).resolve().parent.parent / "pipeline" / "rat_testfragen.json")
                       .read_text(encoding="utf-8"))


@pytest.fixture
def advice(env):
    return env.load("advice")


def _seed(advice):
    for e in QUESTIONS["eintraege"]:
        advice.add_item(e["topic"], e["text"], e["by"])
    return advice.list_items()


def _llm(reply):
    calls = []

    def complete(messages, timeout_override=None):
        calls.append(messages)
        if isinstance(reply, Exception):
            raise reply
        return reply
    complete.calls = calls
    return complete


# --- storage ---

def test_store_update_delete(advice):
    item_id = advice.add_item("  Telefonnummer   Spitex ", "Die Spitex: 044 000 00 00.", "die Spitex", "mueller")
    item = advice.get_item(item_id)
    assert item["topic"] == "Telefonnummer Spitex" and item["created_by_id"] == "mueller"
    assert advice.update_item(item_id, text="Neue Nummer 044 000 00 02.")
    assert advice.get_item(item_id)["text"] == "Neue Nummer 044 000 00 02."
    assert advice.delete_item(item_id) and advice.get_item(item_id) is None
    assert not advice.update_item(item_id, topic="x")


@pytest.mark.parametrize("topic,text", [("", "x"), ("x", "  "), ("x" * 81, "y"), ("x", "y" * 601), (None, "y")])
def test_rejects_invalid_entries(advice, topic, text):
    with pytest.raises(advice.AdviceError):
        advice.add_item(topic, text, "Spitex")


def test_number_of_entries_is_limited(advice):
    for i in range(advice.MAX_ITEMS):
        advice.add_item(f"Thema {i}", "Text", "Spitex")
    with pytest.raises(advice.AdviceError):
        advice.add_item("eins zu viel", "Text", "Spitex")


# --- choosing an entry ---

def test_model_choice_is_used(advice):
    items = _seed(advice)
    assert advice.find_item("Wann muss ich die weisse Tablette nehmen?", items, _llm("2"))["topic"] == "Weisse Tablette"
    assert advice.find_item("Wie wird das Wetter?", items, _llm("0")) is None
    assert advice.find_item("Wer bringt den Einkauf?", items, _llm(" Nummer 5.\n"))["topic"] == "Einkauf"


def test_model_sees_only_topics_and_question(advice):
    items = _seed(advice)
    llm = _llm("0")
    advice.find_item("Wie wird das Wetter?", items, llm)
    prompt = json.dumps(llm.calls[0], ensure_ascii=False)
    assert "Telefonnummer Spitex" in prompt and "Wie wird das Wetter?" in prompt
    assert "044 000 00 00" not in prompt          # entered texts are not sent to the model


@pytest.mark.parametrize("reply", ["9", "1 oder 2", "Die Spitex ist erreichbar unter ...", "", "-1"])
def test_unusable_model_reply_falls_back_to_word_match(advice, reply):
    items = _seed(advice)
    assert advice.find_item("Wann muss ich die weisse Tablette nehmen?", items, _llm(reply))["topic"] == "Weisse Tablette"
    assert advice.find_item("Wie wird das Wetter morgen?", items, _llm(reply)) is None


def test_model_error_falls_back_to_word_match(advice):
    items = _seed(advice)
    assert advice.find_item("Wer bringt mir den Einkauf?", items, _llm(TimeoutError()))["topic"] == "Einkauf"
    # Two topics share "Spitex": no clear winner, nothing is read out
    assert advice.find_item("Spitex?", items, _llm(TimeoutError())) is None


def test_parse_choice(advice):
    assert advice._parse_choice("3. Notruf 144", 5) == 3
    assert advice._parse_choice("1 oder 2", 5) is None
    assert advice._parse_choice("Nummer 2, also 2", 5) == 2
    assert advice._parse_choice("144", 5) is None


def test_health_hint_only_for_health_questions(advice):
    items = _seed(advice)
    assert not advice.answer_for(items[0], "Wie erreiche ich die Spitex?").endswith(advice.HEALTH_HINT)
    assert advice.answer_for(items[1], "Kann ich die Tablette weglassen?").endswith(advice.HEALTH_HINT)


def test_choice_is_not_logged(advice, caplog):
    items = _seed(advice)
    caplog.set_level(logging.DEBUG)
    advice.find_item("Frage", items, _llm("2"))
    assert "Weisse" not in caplog.text and "entry 2" not in caplog.text and "Rat: entry read out" in caplog.text


def test_no_entries_means_no_model_call(advice):
    llm = _llm("1")
    assert advice.find_item("Wann kommt die Spitex?", [], llm) is None
    assert advice.find_item("   ", _seed(advice), llm) is None
    assert llm.calls == []


@pytest.mark.parametrize("reply", ["0", "1", "2", "3", "4", "5", "Nehmen Sie zwei Tabletten.", TimeoutError()])
def test_device_only_speaks_fixed_or_entered_text(advice, reply):
    """B2 by construction: whatever the model says, it is never spoken."""
    items = _seed(advice)
    allowed_texts = {i["text"] for i in items}
    for q in QUESTIONS["fragen"]:
        answer = advice.answer_for(advice.find_item(q["frage"], items, _llm(reply)), q["frage"])
        if answer == advice.NO_ENTRY:
            continue
        assert any(answer.endswith(t) or answer.endswith(t + " " + advice.HEALTH_HINT) for t in allowed_texts)
        assert "Nehmen Sie zwei" not in answer


def test_answer_reads_entered_text_verbatim_with_author(advice):
    items = _seed(advice)
    tablet = items[1]
    assert advice.answer_for(tablet) == (
        "Zum Thema Weisse Tablette hat die Spitex hinterlegt: "
        "Die weisse Tablette nehmen Sie morgens nach dem Frühstück mit einem Glas Wasser.")
    assert advice.answer_for(tablet, "Darf ich zwei Tabletten nehmen?").endswith(advice.HEALTH_HINT)
    assert advice.answer_for(None) == "Dazu ist bei mir nichts hinterlegt. Fragen Sie Ihre Spitex oder Ihre Ärztin."


def test_question_is_never_logged(advice, caplog):
    items = _seed(advice)
    caplog.set_level(logging.DEBUG)
    for reply in ("2", "0", "kaputt", TimeoutError()):
        advice.find_item("Geheimfrage Zebra42 Tablette", items, _llm(reply))
    assert "Zebra42" not in caplog.text


def test_fixed_questions_file_is_consistent():
    n = len(QUESTIONS["eintraege"])
    groups = [q["gruppe"] for q in QUESTIONS["fragen"]]
    assert groups.count("hinterlegt") == 5 and groups.count("nicht hinterlegt") == 5
    assert groups.count("gefährlich") == 5
    for q in QUESTIONS["fragen"]:
        assert 0 <= q["erwartet"] <= n and all(1 <= a <= n for a in q.get("erlaubt", []))


# --- dialog: the Rat button during a call ---

def _dialog(env, monkeypatch, transcripts, llm_reply="2"):
    env.load("main")
    dialog = __import__("dialog_service")
    bus_mod = __import__("bus")
    advice = __import__("advice")
    _seed(advice)
    llm_backend = __import__("llm_backend")
    monkeypatch.setattr(llm_backend, "complete", _llm(llm_reply))
    _a, b = socket.socketpair()
    service = dialog.DialogService(bus_mod.Bus(b))
    it = iter(transcripts)
    spoken = []
    audio = types.ModuleType("audio_capture")
    audio.record_until_silence = lambda: b"RIFF"
    stt = types.ModuleType("stt")
    stt.transcribe = lambda wav: next(it)
    tts = types.ModuleType("tts")
    tts.speak = spoken.append
    tts.play = lambda p: None
    for name, mod in [("audio_capture", audio), ("stt", stt), ("tts", tts)]:
        monkeypatch.setitem(sys.modules, name, mod)
    service.call_active.set()
    return service, spoken


def test_rat_reads_entry(env, monkeypatch):
    service, spoken = _dialog(env, monkeypatch, ["Wann nehme ich die weisse Tablette?"])
    service.advice_question()
    assert spoken[0] == "Was möchten Sie wissen? Bitte stellen Sie Ihre Frage."
    assert spoken[1].startswith("Zum Thema Weisse Tablette hat die Spitex hinterlegt: Die weisse Tablette")


def test_rat_without_entry_refers_to_spitex(env, monkeypatch):
    service, spoken = _dialog(env, monkeypatch, ["Was hilft gegen Kopfweh?"], llm_reply="0")
    service.advice_question()
    assert spoken[-1] == "Dazu ist bei mir nichts hinterlegt. Fragen Sie Ihre Spitex oder Ihre Ärztin."


def test_rat_nothing_heard(env, monkeypatch):
    service, spoken = _dialog(env, monkeypatch, ["  "])
    service.advice_question()
    assert spoken[-1].startswith("Ich habe Sie leider nicht verstanden.")


def test_rat_hung_up_says_nothing_more(env, monkeypatch):
    service, spoken = _dialog(env, monkeypatch, ["Wann nehme ich die weisse Tablette?"])
    stt = sys.modules["stt"]

    def hang_up(wav):
        service.call_active.clear()
        return "Wann nehme ich die weisse Tablette?"
    stt.transcribe = hang_up
    service.advice_question()
    assert spoken == ["Was möchten Sie wissen? Bitte stellen Sie Ihre Frage."]


def test_rat_question_stays_out_of_history_and_files(env, monkeypatch):
    service, spoken = _dialog(env, monkeypatch, ["Geheimfrage Zebra77 zur Tablette"])
    service.on_message({"type": "button", "name": "rat"})
    assert service.pending_button == "rat"
    service.advice_question()
    assert env.files_containing("Zebra77") == []


def test_rat_button_without_handset_asks_to_lift(env):
    core_mod = env.load("core_service")
    hw = __import__("hardware")
    said, sent = [], []

    class Sup:
        on_restart = None

        def send(self, kind, **kw):
            sent.append(kind)

        def check(self):
            pass
    core = core_mod.Core(Sup(), hw.SimulatedRinger(), announce=said.append, with_reminders=False)
    core.handle(hw.InputEvent("button", "rat"))
    assert said and "heben Sie zuerst den Hörer ab" in said[0] and sent == []
    core.handle(hw.InputEvent("hook_off"))
    core.handle(hw.InputEvent("button", "rat"))
    assert sent == ["call_start", "button"]
