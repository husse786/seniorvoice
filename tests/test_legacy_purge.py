"""Decision F2: conversation data stored by the FS26 version is deleted once."""

import json
import sqlite3

SECRET_TEXT = "Ich nehme Marcoumar LegacySecret123"
SECRET_FACT = "Diabetes LegacyFact456"


def _create_fs26_leftovers(env):
    env.db_path.parent.mkdir(parents=True)
    conn = sqlite3.connect(env.db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL DEFAULT '2026-05-01T10:00:00',
            trigger_type TEXT NOT NULL,
            user_text TEXT NOT NULL DEFAULT '',
            response_text TEXT NOT NULL DEFAULT '',
            stt_duration_ms INTEGER, llm_duration_ms INTEGER,
            tts_duration_ms INTEGER, total_duration_ms INTEGER,
            error TEXT DEFAULT NULL);
        CREATE TABLE user_facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT NOT NULL,
            key TEXT NOT NULL, value TEXT NOT NULL, source TEXT DEFAULT '',
            created_at TEXT, updated_at TEXT, active INTEGER NOT NULL DEFAULT 1);
    """)
    for i in range(50):
        conn.execute(
            "INSERT INTO interactions (trigger_type, user_text, response_text, llm_duration_ms) "
            "VALUES ('pir', ?, ?, 900)",
            (f"{SECRET_TEXT} {i}", f"Antwort {SECRET_TEXT} {i}"),
        )
    conn.execute(
        "INSERT INTO user_facts (category, key, value, active) VALUES ('gesundheit', 'krankheit', ?, 0)",
        (SECRET_FACT,),
    )
    conn.commit()
    conn.close()

    pending = env.db_path.parent / "pending_extractions"
    pending.mkdir()
    (pending / "timeout-1.json").write_text(
        json.dumps([{"role": "user", "content": SECRET_TEXT}]), encoding="utf-8"
    )

    env.log_dir.mkdir()
    (env.log_dir / "pipeline.log").write_text(f"INFO: User said: {SECRET_TEXT}\n")
    (env.log_dir / "pipeline.log.1").write_text(f"INFO: Response: {SECRET_TEXT}\n")

    legacy_out = env.tmp / "legacy_out"
    legacy_out.mkdir()
    (legacy_out / "response.wav").write_bytes(b"RIFF" + SECRET_TEXT.encode())
    return legacy_out


def test_legacy_data_removed(env, monkeypatch):
    legacy_out = _create_fs26_leftovers(env)
    privacy = env.load("privacy_migration")
    monkeypatch.setattr(privacy, "_LEGACY_OUTPUT_DIR", legacy_out)

    privacy.run_legacy_purge()

    assert env.files_containing("LegacySecret123") == []
    assert env.files_containing("LegacyFact456") == []
    assert not (env.db_path.parent / "pending_extractions").exists()
    assert not (legacy_out / "response.wav").exists()

    conn = sqlite3.connect(env.db_path)
    # Timings survive for Grafana, text is gone
    assert conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0] == 50
    assert conn.execute(
        "SELECT COUNT(*) FROM interactions WHERE user_text != '' OR response_text != ''"
    ).fetchone()[0] == 0
    # PR 2: the FS26 table is gone entirely (replaced by memory_items)
    assert conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name = 'user_facts'"
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM privacy_meta WHERE key = ?", (privacy.PURGE_MARKER,)
    ).fetchone()[0] == 1
    conn.close()


def test_purge_runs_only_once(env, monkeypatch):
    legacy_out = _create_fs26_leftovers(env)
    privacy = env.load("privacy_migration")
    monkeypatch.setattr(privacy, "_LEGACY_OUTPUT_DIR", legacy_out)
    privacy.run_legacy_purge()

    # New, legitimate log content after the purge must not be wiped on restart
    log_file = env.log_dir / "pipeline.log"
    log_file.write_text("INFO: Interaction complete (stt=1ms)\n")
    privacy.run_legacy_purge()
    assert "Interaction complete" in log_file.read_text()


def test_purge_on_fresh_device(env):
    privacy = env.load("privacy_migration")
    privacy.run_legacy_purge()  # no DB, no logs: must not fail
    conn = sqlite3.connect(env.db_path)
    keys = {r[0] for r in conn.execute("SELECT key FROM privacy_meta")}
    assert privacy.PURGE_MARKER in keys
    conn.close()


def test_leftover_audio_removed_on_every_start(env):
    privacy = env.load("privacy_migration")
    privacy.run_legacy_purge()
    env.output_dir.mkdir(parents=True, exist_ok=True)
    leftover = env.output_dir / "response-abc.wav"
    leftover.write_bytes(b"RIFF")
    privacy.run_legacy_purge()
    assert not leftover.exists()


def test_purge_failure_is_not_marked_done(env, monkeypatch):
    legacy_out = _create_fs26_leftovers(env)
    privacy = env.load("privacy_migration")
    monkeypatch.setattr(privacy, "_LEGACY_OUTPUT_DIR", legacy_out)

    def broken_rmtree(path):
        raise PermissionError("read-only")
    monkeypatch.setattr(privacy.shutil, "rmtree", broken_rmtree)
    import pytest
    with pytest.raises(PermissionError):
        privacy.run_legacy_purge()
    conn = sqlite3.connect(env.db_path)
    assert conn.execute("SELECT COUNT(*) FROM privacy_meta").fetchone()[0] == 0
    conn.close()


def test_blocked_checkpoint_refuses_start(env, monkeypatch):
    _create_fs26_leftovers(env)
    privacy = env.load("privacy_migration")
    monkeypatch.setattr(privacy, "checkpoint_truncate", lambda conn, retries=10: False)
    import pytest
    with pytest.raises(RuntimeError):
        privacy.run_legacy_purge()
