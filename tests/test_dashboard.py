from applicant_zero.dashboard import build_brief_page, build_page
from applicant_zero.profile import RISHI_PROFILE
from applicant_zero.scoring import Job, score_job
import sqlite3

from applicant_zero.storage import initialise_database, list_matches, save_match, update_workflow


def test_empty_dashboard_has_guidance(tmp_path):
    page = build_page(tmp_path / "missing.sqlite3")
    assert "No jobs collected yet" in page


def test_dashboard_includes_local_workflow_tracker(tmp_path):
    database = initialise_database(tmp_path / "jobs.sqlite3")
    job = Job("job-1", "Data Analyst", "Example", "Sydney", "test", "https://example.invalid", "SQL and Power BI")
    save_match(database, job, score_job(job, RISHI_PROFILE))
    update_workflow(database, "job-1", "Preparing", "Check the Excel requirement")
    rows = list_matches(database)
    assert rows[0]["workflow_status"] == "Preparing"
    assert rows[0]["notes"] == "Check the Excel requirement"
    page = build_page(tmp_path / "jobs.sqlite3")
    assert "Your tracker" in page
    assert "Insights" in page
    assert "Jobs collected" in page
    assert "Preparing" in page
    brief = build_brief_page(tmp_path / "jobs.sqlite3", "job-1")
    assert "Before applying" in brief
    assert "SQL and Power BI" in brief


def test_existing_database_is_upgraded_for_the_tracker(tmp_path):
    path = tmp_path / "old.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE job_matches (external_id TEXT PRIMARY KEY)")
    with initialise_database(path) as connection:
        fields = {row[1] for row in connection.execute("PRAGMA table_info(job_matches)")}
    assert {"workflow_status", "notes"}.issubset(fields)
