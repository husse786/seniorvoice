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
    assert groups.count("notfall") >= 3
    for q in QUESTIONS["fragen"]:
        assert q["erwartet"] == "notfall" or 0 <= q["erwartet"] <= n
        assert all(1 <= a <= n for a in q.get("erlaubt", []))


# --- emergencies (T12): word list before the model ---

@pytest.mark.parametrize("question", [
    "Ich habe Schmerzen in der Brust, was soll ich tun?",
    "Ich bin gestürzt und komme nicht mehr hoch.",
    "Ich bin hingefallen",
    "Ich bekomme so schlecht Luft",
    "Ich habe Atemnot",
    "Mir wird schwarz vor Augen",
    "Mein Mann ist bewusstlos",
    "Mein Arm ist ganz gelähmt",
    "Ich glaube, ich habe einen Schlaganfall",
    "Es blutet stark",
    "Ich habe aus Versehen zu viele Tabletten genommen",
    "Ist das ein Notfall?",
    "Ich will nicht mehr leben",
    "BRUSTSCHMERZEN!",
])
def test_emergency_words_point_to_help_and_144(advice, question):
    _seed(advice)
    assert advice.is_emergency(question)
    assert advice.reply_for(question, complete=_llm("0")) == [advice.EMERGENCY]


@pytest.mark.parametrize("question", [
    "Mein Herz schmerzt", "Ich habe Schmerzen im Herz", "Ich hatte einen Unfall",
    "Ich liege auf dem Boden", "Ich bin ausgerutscht", "Mein Mann reagiert nicht mehr",
    "Ich kann mich nicht bewegen", "Ich habe Nasenbluten und eine Nasenblutung",
])
def test_more_emergency_phrasings(advice, question):
    assert advice.is_emergency(question)


@pytest.mark.parametrize("question", [
    "Wann kommt die Haushaltshilfe?", "Ist die Physiotherapie heute ausgefallen?",
    "Mir ist eingefallen, wann kommt die Spitex?", "Hat Ihnen das gefallen?",
    "Wann soll ich Staub saugen?", "Wann kommt die Spitex?", "Wer bringt den Einkauf?",
    "Wann muss ich die weisse Tablette nehmen?", "Wie ist das Wetter?",
])
def test_everyday_questions_are_not_emergencies(advice, question):
    assert not advice.is_emergency(question)


def test_emergency_hint_does_not_depend_on_the_model(advice):
    _seed(advice)
    assert advice.reply_for("Ich bin gestürzt", complete=_llm(TimeoutError())) == [advice.EMERGENCY]
    assert advice.reply_for("Ich bin gestürzt", complete=_llm("Alles gut, ruhen Sie sich aus.")) == [advice.EMERGENCY]


def test_entered_emergency_number_is_still_read(advice):
    item_id = advice.add_item("Notfallnummer Hausarzt", "Notfallnummer: 044 000 00 09.", "Ihre Tochter")
    items = advice.list_items()
    sentences = advice.reply_for("Was ist die Notfallnummer meiner Ärztin?", items, _llm("1"))
    assert sentences[0] == advice.EMERGENCY
    assert sentences[1].endswith("Notfallnummer: 044 000 00 09.") and item_id


def test_emergency_sentence(advice):
    assert advice.EMERGENCY == ("Wenn es ein Notfall ist, drücken Sie sofort den Hilfe-Knopf "
                                "oder rufen Sie 144 an.")


def test_fixed_questions_emergency_detection(advice):
    """Word list alone: every emergency question caught, no other question."""
    for q in QUESTIONS["fragen"]:
        assert advice.is_emergency(q["frage"]) == (q["erwartet"] == "notfall"), q["frage"]


def test_emergency_is_not_logged(advice, caplog):
    _seed(advice)
    caplog.set_level(logging.DEBUG)
    advice.reply_for("Ich bin gestürzt", advice.list_items(), _llm("1"))
    assert "gestürzt" not in caplog.text and "Notfall" not in caplog.text


# --- what the device says when Rat is pressed (decision 19.11.2026) ---

def _items(*topics):
    return [{"topic": t, "text": "x", "created_by": "Spitex"} for t in topics]


def test_ask_without_entries_is_the_plain_question(advice):
    assert advice.ask_for([]) == advice.ASK


@pytest.mark.parametrize("topics, named", [
    (("Trinken",), "Trinken"),
    (("Trinken", "Spitex"), "Trinken und Spitex"),
    (("Trinken", "Spitex", "Einkauf"), "Trinken, Spitex und Einkauf"),
    (("A", "B", "C", "D", "E", "F"), "A, B, C, D, E und einem weiteren Thema"),
    (("A", "B", "C", "D", "E", "F", "G", "H"), "A, B, C, D, E und 3 weiteren Themen"),
    (("Trinken.", "Spitex: ", "?"), "Trinken und Spitex"),
])
def test_ask_names_topics(advice, topics, named):
    assert advice.ask_for(_items(*topics)) == (
        f"Ich kann Ihnen etwas sagen zu: {named}. Was möchten Sie wissen?")


def test_ask_never_reads_entered_texts(advice):
    items = [{"topic": "Weisse Tablette", "text": "Zwei Stück morgens", "created_by": "Spitex"}]
    assert "Zwei" not in advice.ask_for(items)


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
    assert spoken[0] == ("Ich kann Ihnen etwas sagen zu: Telefonnummer Spitex, Weisse Tablette, Besuch der Spitex, Hausarztpraxis und Einkauf. Was möchten Sie wissen?")
    assert spoken[1].startswith("Zum Thema Weisse Tablette hat die Spitex hinterlegt: Die weisse Tablette")


def test_rat_without_entries_asks_plainly(env, monkeypatch):
    service, spoken = _dialog(env, monkeypatch, ["Wann kommt die Spitex?"], llm_reply="0")
    advice = sys.modules["advice"]
    for item in advice.list_items():
        advice.delete_item(item["id"])
    service.advice_question()
    assert spoken == [advice.ASK, advice.NO_ENTRY]


def test_rat_entries_unreadable_still_asks(env, monkeypatch):
    service, spoken = _dialog(env, monkeypatch, ["Ich bin gestürzt"])
    advice = sys.modules["advice"]

    def broken():
        raise RuntimeError("db locked")
    monkeypatch.setattr(advice, "list_items", broken)
    service.advice_question()
    assert spoken == [advice.ASK, advice.EMERGENCY]


def test_rat_emergency_in_call(env, monkeypatch):
    service, spoken = _dialog(env, monkeypatch, ["Ich habe starke Schmerzen in der Brust"], llm_reply="0")
    service.advice_question()
    assert spoken[1:] == ["Wenn es ein Notfall ist, drücken Sie sofort den Hilfe-Knopf oder rufen Sie 144 an."]


def test_rat_emergency_spoken_before_model_is_asked(env, monkeypatch):
    service, spoken = _dialog(env, monkeypatch, ["Ich bin gestürzt"])
    llm_backend = sys.modules["llm_backend"]

    def complete(messages, timeout_override=None):
        assert spoken[-1] == sys.modules["advice"].EMERGENCY   # already said
        raise TimeoutError()
    monkeypatch.setattr(llm_backend, "complete", complete)
    service.advice_question()
    assert spoken[-1] == sys.modules["advice"].EMERGENCY


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
    assert spoken == ["Ich kann Ihnen etwas sagen zu: Telefonnummer Spitex, Weisse Tablette, Besuch der Spitex, Hausarztpraxis und Einkauf. Was möchten Sie wissen?"]


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


# --- R3: the same emergency hint in the normal conversation (Sprechen) ---

@pytest.fixture
def turn(env, monkeypatch):
    """One conversation turn through run_pipeline with stubbed audio and LLM."""
    main = env.load("main")
    dialog = __import__("dialog_service")
    a, b = socket.socketpair()
    service = dialog.DialogService(__import__("bus").Bus(b))
    service.call_active.set()
    events = []
    state = {"active": True, "llm": "Das tut mir leid.", "said": ""}

    def speak(t):
        events.append(("speak", t))
    for name, attrs in {
        "audio_capture": {"record_until_silence": lambda: b"RIFF"},
        "stt": {"transcribe": lambda wav: state["said"]},
        "tts": {"speak": lambda t: speak(t)},
    }.items():
        mod = types.ModuleType(name)
        for k, v in attrs.items():
            setattr(mod, k, v)
        monkeypatch.setitem(sys.modules, name, mod)
    import llm_client

    def chat(text, history, facts_block=""):
        events.append(("llm", text, facts_block))
        if isinstance(state["llm"], Exception):
            raise state["llm"]
        return state["llm"], history + [{"role": "user", "content": text},
                                        {"role": "assistant", "content": state["llm"]}]
    monkeypatch.setattr(llm_client, "chat", chat)
    monkeypatch.setattr(main, "LLM_STREAM", False)

    def run(said, history=None, **kw):
        state["said"] = said
        kw.setdefault("notice", service.notice)
        return main.run_pipeline(False, history or [], trigger="handset",
                                 still_active=lambda: state["active"], **kw)
    run.events, run.state, run.service, run.main = events, state, service, main
    yield run
    a.close()
    b.close()


def test_conversation_emergency_hint_before_the_model(turn):
    turn("Ich habe so Schmerzen in der Brust")
    advice = sys.modules["advice"]
    assert turn.events[0] == ("speak", advice.EMERGENCY)
    assert turn.events[1][0] == "llm"                        # the conversation goes on
    assert turn.main.NOTICE_GIVEN_PROMPT in turn.events[1][2]  # model knows about the hint
    assert turn.events[-1] == ("speak", "Das tut mir leid.")


def test_conversation_without_emergency_has_no_hint(turn):
    turn.state["llm"] = "Sonnig."
    turn("Wie wird das Wetter morgen?")
    assert [e for e in turn.events if e[0] == "speak"] == [("speak", "Sonnig.")]
    assert turn.main.NOTICE_GIVEN_PROMPT not in turn.events[0][2]


def test_conversation_hint_even_if_model_fails(turn):
    turn.state["llm"] = TimeoutError()
    with pytest.raises(TimeoutError):
        turn("Ich bin gestürzt")
    assert turn.events[0] == ("speak", sys.modules["advice"].EMERGENCY)


def test_conversation_hint_once_per_call(turn):
    turn("Ich bin gestürzt")
    turn("Seit dem Sturz habe ich Angst")
    hints = [e for e in turn.events if e == ("speak", sys.modules["advice"].EMERGENCY)]
    assert len(hints) == 1


def test_hang_up_during_hint_stops_the_turn(turn):
    def speak_and_hang_up(t):
        turn.events.append(("speak", t))
        turn.state["active"] = False
    sys.modules["tts"].speak = speak_and_hang_up
    history, _ = turn("Ich bin gestürzt", history=[])
    assert [e[0] for e in turn.events] == ["speak"] and history == []


def test_default_notice_without_dialog_service(turn):
    """FS26 mode (main.py) gets the hint too: it is run_pipeline's default."""
    turn("Ich bin hingefallen", notice=None)
    assert turn.events[0] == ("speak", sys.modules["advice"].EMERGENCY)


@pytest.mark.parametrize("said", [
    "Danke für die Hilfe, tschüss", "Die Tauben auf dem Balkon", "Heute gibt es Pouletbrust",
    "Ich habe Krampfadern", "Das kostet 144 Franken", "Der Teppich am Boden ist neu",
    "Mein Mann ist vor fünf Jahren gestorben",
])
def test_everyday_conversation_gives_no_hint(turn, said):
    turn.state["llm"] = "Aha."
    turn(said)
    assert [e for e in turn.events if e[0] == "speak"] == [("speak", "Aha.")]


def test_family_dictation_gets_the_hint(env, monkeypatch):
    service, spoken = _dialog(env, monkeypatch, ["Ich bin hingefallen, komm bitte", "Nein"])
    __import__("help_alert").set_contacts([{"name": "Sandra", "role": "Tochter", "address": "x"}])
    service.family_message()
    assert sys.modules["advice"].EMERGENCY in spoken
