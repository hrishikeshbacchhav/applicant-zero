import json

from applicant_zero.profile import RISHI_PROFILE
from applicant_zero.scoring import Job, score_job
from applicant_zero.session_trace import append_trace, load_trace, start_trace
from applicant_zero.storage import initialise_database, save_match


def test_session_trace_is_private_and_append_only(tmp_path):
    database_path = tmp_path / "data" / "jobs.sqlite3"
    with initialise_database(database_path) as database:
        job = Job("job-1", "Data Analyst", "Example", "Sydney", "test", "https://example.invalid", "SQL")
        save_match(database, job, score_job(job, RISHI_PROFILE))

    path = start_trace(database_path, "job-1", "Lever", "https://example.invalid/apply")
    append_trace(database_path, "job-1", "required_question", "Review a required question.", "https://example.invalid/apply")

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["job"]["company"] == "Example"
    assert payload["events"][0]["event"] == "required_question"
    assert load_trace(database_path, "job-1") == payload
