import sqlite3

from applicant_zero.runtime import backup_database, database_path, prepare_state


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
