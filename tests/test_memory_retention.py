"""Decision A8: notes max. 7 days, real deletion, no health data, "Vergiss das"."""

import json
import sqlite3
import sys
import types
from datetime import datetime, timedelta, timezone

import pytest

from conftest import patch_http

T0 = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def memory(env, monkeypatch):
    mem = env.load("memory")
    clock = {"now": T0}
    monkeypatch.setattr(mem, "_now", lambda: clock["now"])
    mem.clock = clock
    return mem


def test_note_expires_after_7_days(env, memory):
    memory.store_facts([{"category": "persoenlich", "key": "name", "value": "Albert Notiz7781"}])
    assert memory.load_facts() == [{"category": "persoenlich", "key": "name", "value": "Albert Notiz7781"}]

    memory.clock["now"] = T0 + timedelta(days=6, hours=23)
    assert len(memory.load_facts()) == 1

    memory.clock["now"] = T0 + timedelta(days=8)
    assert memory.load_facts() == []          # not used any more
    assert memory.purge_expired() == 1        # and really deleted
    assert env.files_containing("Notiz7781") == []


def test_retention_capped_at_7_days(env, monkeypatch):
    env.set(MEMORY_RETENTION_DAYS="30")
    mem = env.load("memory")
    monkeypatch.setattr(mem, "_now", lambda: T0)
    assert mem.retention_days() == 7


def test_new_value_replaces_old_for_real(env, memory):
    memory.store_facts([{"category": "vorlieben", "key": "musik", "value": "Jodel AltWert11"}])
    memory.store_facts([{"category": "vorlieben", "key": "musik", "value": "Klassik"}])
    assert memory.load_facts()[0]["value"] == "Klassik"
    assert env.files_containing("AltWert11") == []


@pytest.mark.parametrize("fact", [
    {"category": "gesundheit", "key": "krankheit", "value": "Diabetes"},
    {"category": "persoenlich", "key": "medikament", "value": "Marcoumar"},
    {"category": "sonstiges", "key": "info", "value": "hat Schmerzen im Knie"},
    {"category": "kontakte", "key": "hausarzt", "value": "Dr. Meier"},
    {"category": "termine", "key": "kontrolle", "value": "Montag 10 Uhr"},
    {"category": "vorlieben", "key": "getraenk", "value": "Tee ohne Zucker"},
])
def test_health_and_appointments_not_stored(memory, fact):
    assert memory.store_facts([fact]) == 0
    assert memory.load_facts() == []


@pytest.mark.parametrize("fact", [
    {"category": "persoenlich", "key": "name", "value": "Albert"},
    {"category": "vorlieben", "key": "hobby", "value": "Fernsehen und Jassen"},
    {"category": "kontakte", "key": "tochter", "value": "Sandra"},
])
def test_normal_notes_are_stored(memory, fact):
    assert memory.store_facts([fact]) == 1


def test_forget_all_deletes_immediately(env, memory):
    memory.store_facts([
        {"category": "persoenlich", "key": "name", "value": "Albert Vergiss555"},
        {"category": "kontakte", "key": "tochter", "value": "Sandra"},
    ])
    assert memory.forget_all() == 2
    assert memory.load_facts() == []
    assert env.files_containing("Vergiss555") == []


def test_failed_extraction_kept_in_ram_only(env, memory, monkeypatch):
    def broken(messages):
        raise RuntimeError("ollama down")
    monkeypatch.setattr(memory, "_call_llm_for_extraction", broken)
    monkeypatch.setattr(memory.time, "sleep", lambda s: None)
    memory.extract_and_store_facts([{"role": "user", "content": "Ich heisse Albert Puffer999"}])
    assert len(memory._pending) == 1
    assert env.files_containing("Puffer999") == []

    # Next start: model is back, the buffered conversation is extracted
    monkeypatch.setattr(
        memory, "_call_llm_for_extraction",
        lambda m: json.dumps([{"category": "persoenlich", "key": "name", "value": "Albert"}]),
    )
    memory.retry_pending_extractions()
    assert memory._pending == []
    assert memory.load_facts()[0]["value"] == "Albert"


def test_extraction_filters_health_from_llm_output(memory, monkeypatch):
    monkeypatch.setattr(memory, "_call_llm_for_extraction", lambda m: json.dumps([
        {"category": "persoenlich", "key": "name", "value": "Albert"},
        {"category": "gesundheit", "key": "blutdruck", "value": "180/110"},
    ]))
    memory.extract_and_store_facts([{"role": "user", "content": "..."}])
    assert [f["key"] for f in memory.load_facts()] == ["name"]


def test_fs26_user_facts_table_dropped(env):
    env.db_path.parent.mkdir(parents=True)
    conn = sqlite3.connect(env.db_path)
    conn.execute("CREATE TABLE user_facts (id INTEGER PRIMARY KEY, category TEXT, key TEXT, value TEXT, active INTEGER)")
    conn.execute("INSERT INTO user_facts (category, key, value, active) VALUES ('gesundheit','x','Alt888',1)")
    conn.commit()
    conn.close()
    privacy = env.load("privacy_migration")
    privacy.run_legacy_purge()
    conn = sqlite3.connect(env.db_path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert "user_facts" not in tables
    assert env.files_containing("Alt888") == []


# --- "Vergiss das" by voice, end to end through main.run_pipeline ---

def _run_turn(env, monkeypatch, sentence, history=None):
    main = env.load("main")
    spoken = []
    audio = types.ModuleType("audio_capture")
    audio.record_until_silence = lambda: b"RIFF"
    stt = types.ModuleType("stt")
    stt.transcribe = lambda wav: sentence
    tts = types.ModuleType("tts")
    tts.speak = lambda text: spoken.append(text)
    tts.play = lambda path: None
    for name, mod in [("audio_capture", audio), ("stt", stt), ("tts", tts)]:
        monkeypatch.setitem(sys.modules, name, mod)
    monkeypatch.setattr("builtins.input", lambda *a: "")

    import llm_backend
    llm_calls = []

    def urlopen(req, timeout=None):
        llm_calls.append(1)
        raise OSError("LLM must not be called for forget commands")
    patch_http(llm_backend, monkeypatch, urlopen)
    result = main.run_pipeline(use_pir=False, history=history or [])
    return main, result, spoken, llm_calls


def test_vergiss_alles_by_voice(env, monkeypatch):
    mem = env.load("memory")
    mem.store_facts([{"category": "persoenlich", "key": "name", "value": "Albert"}])
    main, (history, pre_reset), spoken, llm_calls = _run_turn(env, monkeypatch, "Vergiss alles.")
    import memory
    assert memory.load_facts() == []
    assert spoken == [main.FORGET_ALL_REPLY]
    assert llm_calls == []
    assert history == [] and pre_reset is None


def test_vergiss_das_drops_current_conversation(env, monkeypatch):
    earlier = [
        {"role": "user", "content": "Meine Nachbarin heisst Rosa"},
        {"role": "assistant", "content": "Schön."},
    ]
    main, (history, pre_reset), spoken, llm_calls = _run_turn(
        env, monkeypatch, "Bitte vergessen Sie das.", history=earlier)
    assert history == [] and pre_reset is None   # nothing left to extract
    assert spoken == [main.FORGET_THIS_REPLY]
    assert llm_calls == []


@pytest.mark.parametrize("text,expected", [
    ("Vergiss das.", "this"),
    ("Vergessen Sie das bitte", "this"),
    ("Vergiss alles!", "all"),
    ("Vergiss das nicht, morgen kommt Sandra", None),
    ("Ich vergesse das immer", None),
])
def test_forget_phrase_detection(env, text, expected):
    main = env.load("main")
    assert main._check_forget(text) == expected
