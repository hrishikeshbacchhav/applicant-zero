import sqlite3

import json

from applicant_zero.runtime import backup_database, database_path, prepare_state, recover_database, synchronise_board_registry


def test_prepare_state_copies_legacy_private_state_once(tmp_path, monkeypatch):
    repository = tmp_path / "repository"
    (repository / "private").mkdir(parents=True)
    (repository / "private" / "candidate_profile.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("APPLICANT_ZERO_STATE_DIR", str(tmp_path / "runtime"))

    state = prepare_state(repository)

    assert (state / "private" / "candidate_profile.json").exists()
    assert database_path(repository) == state / "data" / "applicant_zero.sqlite3"


def test_backup_database_uses_a_valid_sqlite_snapshot(tmp_path, monkeypatch):
    repository = tmp_path / "repository"
    monkeypatch.setenv("APPLICANT_ZERO_STATE_DIR", str(tmp_path / "runtime"))
    database = database_path(repository)
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE example (value TEXT)")
        connection.execute("INSERT INTO example VALUES ('kept')")

    backup = backup_database(repository, "test")

    assert backup is not None and backup.exists()
    with sqlite3.connect(backup) as connection:
        assert connection.execute("SELECT value FROM example").fetchone()[0] == "kept"


def test_corrupt_database_is_preserved_and_restored_from_valid_snapshot(tmp_path, monkeypatch):
    repository = tmp_path / "repository"
    monkeypatch.setenv("APPLICANT_ZERO_STATE_DIR", str(tmp_path / "runtime"))
    database = database_path(repository)
    connection = sqlite3.connect(database)
    try:
        connection.execute("CREATE TABLE example (value TEXT)")
        connection.execute("INSERT INTO example VALUES ('restored')")
        connection.commit()
    finally:
        connection.close()
    backup = backup_database(repository, "test")
    assert backup is not None
    database.write_bytes(b"not a sqlite database")

    message = recover_database(repository)

    assert "Recovered your local tracker" in message
    assert list(database.parent.glob("applicant_zero.corrupt-*.sqlite3"))
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT value FROM example").fetchone()[0] == "restored"


def test_board_registry_merges_new_starters_without_losing_custom_board(tmp_path, monkeypatch):
    repository = tmp_path / "repository"
    (repository / "data").mkdir(parents=True)
    (repository / "data" / "company_boards.starter.json").write_text(
        json.dumps([{"company": "Verified", "ats": "lever", "token": "verified"}]), encoding="utf-8"
    )
    monkeypatch.setenv("APPLICANT_ZERO_STATE_DIR", str(tmp_path / "runtime"))
    state = prepare_state(repository)
    private = state / "data" / "company_boards.json"
    private.write_text(json.dumps([{"company": "Candidate board", "ats": "ashby", "token": "candidate"}]), encoding="utf-8")

    path = synchronise_board_registry(repository)

    companies = {row["company"] for row in json.loads(path.read_text(encoding="utf-8"))}
    assert companies == {"Candidate board", "Verified"}
