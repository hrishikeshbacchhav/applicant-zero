from applicant_zero.runtime import database_path, prepare_state


def test_prepare_state_copies_legacy_private_state_once(tmp_path, monkeypatch):
    repository = tmp_path / "repository"
    (repository / "private").mkdir(parents=True)
    (repository / "private" / "candidate_profile.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("APPLICANT_ZERO_STATE_DIR", str(tmp_path / "runtime"))

    state = prepare_state(repository)

    assert (state / "private" / "candidate_profile.json").exists()
    assert database_path(repository) == state / "data" / "applicant_zero.sqlite3"
