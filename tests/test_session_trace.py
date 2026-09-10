import json

from applicant_zero.profile import RISHI_PROFILE
from applicant_zero.scoring import Job, score_job
from applicant_zero.session_trace import append_trace, load_trace, record_form_inventory, start_trace
from applicant_zero.platform_pilots import form_knowledge
from applicant_zero.storage import initialise_database, save_match


def test_session_trace_is_private_and_append_only(tmp_path):
    database_path = tmp_path / "data" / "jobs.sqlite3"
    with initialise_database(database_path) as database:
        job = Job("job-1", "Data Analyst", "Example", "Sydney", "test", "https://example.invalid", "SQL")
        save_match(database, job, score_job(job, RISHI_PROFILE))

    path = start_trace(database_path, "job-1", "Lever", "https://example.invalid/apply")
    append_trace(database_path, "job-1", "required_question", "Review a required question.", "https://example.invalid/apply")
    record_form_inventory(database_path, "job-1", "https://example.invalid/apply", [{"label": "Email", "control": "email", "required": True, "handling": "recognised"}])

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["job"]["company"] == "Example"
    assert payload["events"][0]["event"] == "required_question"
    assert payload["form_pages"][0]["fields"][0]["handling"] == "recognised"
    assert load_trace(database_path, "job-1") == payload


def test_repeated_unchanged_form_page_is_not_added_twice(tmp_path):
    database_path = tmp_path / "data" / "jobs.sqlite3"
    with initialise_database(database_path) as database:
        job = Job("job-1", "Data Analyst", "Example", "Sydney", "test", "https://example.invalid", "SQL")
        save_match(database, job, score_job(job, RISHI_PROFILE))
    start_trace(database_path, "job-1", "Lever", "https://example.invalid/apply")
    fields = [{"label": "Email", "control": "email", "required": True, "handling": "recognised"}]
    record_form_inventory(database_path, "job-1", "https://example.invalid/apply", fields)
    record_form_inventory(database_path, "job-1", "https://example.invalid/apply", fields)
    trace = load_trace(database_path, "job-1")
    assert len(trace["form_pages"]) == 1
    assert trace["form_pages"][0]["step"] == 1


def test_form_knowledge_aggregates_safe_descriptors_without_answers(tmp_path):
    database_path = tmp_path / "data" / "jobs.sqlite3"
    with initialise_database(database_path) as database:
        job = Job("job-1", "Data Analyst", "Example", "Sydney", "test", "https://example.invalid", "SQL")
        save_match(database, job, score_job(job, RISHI_PROFILE))
    start_trace(database_path, "job-1", "Lever", "https://example.invalid/apply")
    record_form_inventory(database_path, "job-1", "https://example.invalid/apply", [
        {"label": "Email address", "control": "email", "required": True, "handling": "recognised"},
        {"label": "Work rights declaration", "control": "radio", "required": True, "handling": "candidate review"},
    ])
    knowledge = form_knowledge(database_path)
    assert {item["label"] for item in knowledge["Lever"]} == {"email address", "work rights declaration"}
    assert {item["handling"] for item in knowledge["Lever"]} == {"recognised", "candidate review"}
