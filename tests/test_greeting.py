"""Opening on pickup from editable building blocks (prompts/begruessung.txt),
persona from prompts/persona.txt. Nothing of it is hard-coded wording."""

import json
import os
import random
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


ZH = ZoneInfo("Europe/Zurich")
SHIPPED = Path(__file__).resolve().parent.parent / "pipeline" / "prompts"

BLOCKS = """# comment
[nachmittag]
Guten Tag{anrede}.
Hallo {name}, schön.
[termin]
Um {zeit} ist {titel}.
[frage]
Wie geht es Ihnen?
[frage_nachmittag]
Waren Sie draussen?
"""


def _greeter(env, text=BLOCKS, seed=1):
    g = env.load("greeting")
    path = env.tmp / "begruessung.txt"
    path.write_text(text, encoding="utf-8")
    return g, g.Greeter(path, random.Random(seed)), path


def test_time_of_day_boundaries(env):
    g = env.load("greeting")
    assert [g.time_of_day(h) for h in (4, 5, 10, 11, 13, 14, 17, 18, 21, 22)] == [
        "nacht", "morgen", "morgen", "mittag", "mittag", "nachmittag", "nachmittag",
        "abend", "abend", "nacht"]


def test_opening_has_name_appointment_and_question(env):
    g, greeter, _ = _greeter(env)
    now = datetime(2026, 11, 19, 14, 5, tzinfo=ZH)
    text = greeter.compose(now, "Frau Keller", (now.replace(hour=15, minute=30), "Coiffeur"))
    assert "Frau Keller" in text
    assert "Um 15:30 Uhr ist Coiffeur." in text
    assert text.endswith("?")
    assert "{" not in text


def test_without_name_no_dangling_comma_and_name_lines_skipped(env):
    g, greeter, _ = _greeter(env)
    now = datetime(2026, 11, 19, 15, 0, tzinfo=ZH)
    for _ in range(20):
        text = greeter.compose(now)
        assert text.startswith("Guten Tag.") and "Hallo" not in text and " ," not in text


def test_same_variant_never_twice_in_a_row(env):
    g, greeter, _ = _greeter(env, seed=7)
    now = datetime(2026, 11, 19, 15, 0, tzinfo=ZH)
    texts = [greeter.compose(now, "Frau Keller") for _ in range(30)]
    assert all(a != b for a, b in zip(texts, texts[1:]))
    assert len(set(texts)) > 1


def test_edited_file_applies_without_restart(env):
    g, greeter, path = _greeter(env)
    now = datetime(2026, 11, 19, 15, 0, tzinfo=ZH)
    greeter.compose(now)
    path.write_text("[nachmittag]\nSali zäme.\n[frage]\nSchon Kaffee gehabt?\n", encoding="utf-8")
    st = path.stat()
    os.utime(path, (st.st_atime, st.st_mtime + 5))
    assert greeter.compose(now) == "Sali zäme. Schon Kaffee gehabt?"


def test_missing_file_falls_back(env):
    g = env.load("greeting")
    greeter = g.Greeter(env.tmp / "fehlt.txt")
    text = greeter.compose(datetime(2026, 11, 19, 8, 0, tzinfo=ZH), "Herr Meier")
    assert text.startswith("Guten Morgen, Herr Meier.") and text.endswith("?")


def test_shipped_file_is_complete_and_never_offers_help(env):
    g = env.load("greeting")
    blocks = g.parse((SHIPPED / "begruessung.txt").read_text(encoding="utf-8"))
    for key in ("morgen", "mittag", "nachmittag", "abend", "nacht", "termin", "frage"):
        assert blocks.get(key), key
    for lines in blocks.values():
        for line in lines:
            assert "helfen" not in line.lower()
            assert set(re.findall(r"\{([a-z]+)\}", line)) <= {"anrede", "name", "zeit", "titel"}
    persona = (SHIPPED / "persona.txt").read_text(encoding="utf-8")
    assert "Wie kann ich Ihnen helfen" in persona   # named as forbidden


def test_next_appointment_today_from_db(env):
    appointments = env.load("appointments")
    now = datetime(2026, 11, 19, 14, 0, tzinfo=ZH)
    appointments.add_appointment("Zahnarzt", now.replace(hour=9).replace(tzinfo=None), "test", now=now - timedelta(hours=6))
    appointments.add_appointment("Tabletten", now.replace(hour=15).replace(tzinfo=None), "test",
                                 kind="medikament", now=now)
    appointments.add_appointment("Coiffeur", now.replace(hour=15, minute=30).replace(tzinfo=None), "test", now=now)
    appointments.add_appointment("Hausarzt", (now + timedelta(days=1)).replace(tzinfo=None), "test", now=now)
    g = env.load("greeting")
    when, title = g.next_appointment_today(now)
    assert title == "Coiffeur" and (when.hour, when.minute) == (15, 30)
    assert g.next_appointment_today(now.replace(hour=16)) is None


def test_persona_from_file_without_comments(env):
    prompts = env.tmp / "prompts"
    prompts.mkdir()
    (prompts / "persona.txt").write_text("# Kommentar\nDu bist Testpersona.\n", encoding="utf-8")
    env.set(PROMPTS_DIR=prompts)
    llm_client = env.load("llm_client")
    prompt = llm_client.build_system_prompt("", is_first_turn=False)
    assert prompt.startswith("Du bist Testpersona.") and "Kommentar" not in prompt
    (prompts / "persona.txt").unlink()
    assert "SeniorVoice" in llm_client.build_system_prompt("", is_first_turn=False)


def _dialog(env, monkeypatch, requests):
    env.set(GREETING_ON_PICKUP="true", SENIOR_NAME="Frau Keller")
    from test_dialog_service import _setup

    def llm(req, timeout=None):
        requests.append(json.loads(req.data))
        body = json.dumps({"choices": [{"message": {"content": "Schön, das freut mich."}}]}).encode()

        class R:
            def read(self): return body
            def __enter__(self): return self
            def __exit__(self, *a): return False
        return R()
    service, core_bus, spoken, dialog = _setup(env, monkeypatch, "Ja, eine Suppe", llm)
    sys.modules["tts"].speak = spoken.append
    main = sys.modules["main"]
    real = main.run_pipeline

    def one_turn(*a, **kw):
        result = real(*a, **kw)
        service.call_active.clear()          # hang up after the first answer
        return result
    monkeypatch.setattr(main, "run_pipeline", one_turn)
    notes = []
    monkeypatch.setattr(sys.modules["memory"], "extract_facts_async",
                        lambda history, source="": notes.append(history))
    service.notes = notes
    return service, spoken


def test_device_greets_on_pickup_and_llm_knows_it(env, monkeypatch):
    requests = []
    service, spoken = _dialog(env, monkeypatch, requests)
    service.on_message({"type": "call_start"})
    service.run_call()
    assert len(spoken) == 2
    assert "Frau Keller" in spoken[0] and spoken[0].endswith("?")
    messages = requests[0]["messages"]
    assert messages[1] == {"role": "assistant", "content": spoken[0]}
    assert "NICHT erneut" in messages[0]["content"]
    # The greeting itself does not become a note, the senior's answer does
    assert [m["role"] for m in service.notes[0]] == ["user", "assistant"]


def test_no_greeting_after_reminder_but_llm_knows_reminder(env, monkeypatch):
    requests = []
    service, spoken = _dialog(env, monkeypatch, requests)
    reminder = "Guten Tag. Eine Erinnerung: Um 15:30 Uhr haben Sie Coiffeur."
    service.on_message({"type": "call_start", "opened_with": reminder})
    service.run_call()
    assert spoken == ["Schön, das freut mich."]
    assert requests[0]["messages"][1] == {"role": "assistant", "content": reminder}
