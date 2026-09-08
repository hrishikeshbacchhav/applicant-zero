from applicant_zero.dashboard import build_answers_page, build_brief_page, build_page
from applicant_zero.profile import RISHI_PROFILE
from applicant_zero.scoring import Job, score_job
import json
import sqlite3
from unittest.mock import patch

from applicant_zero.storage import (
    get_match,
    initialise_database,
    list_application_events,
    list_matches,
    mark_company_jobs_inactive,
    save_match,
    update_workflow,
)


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
    assert "Current listings" in page
    assert "Live sources" in page
    assert "Search role, company or location" in page
    assert "All companies" in page
    assert "All tracker stages" in page
    assert "Preparing" in page
    brief = build_brief_page(tmp_path / "jobs.sqlite3", "job-1")
    assert "Before applying" in brief
    assert "Application compatibility" in brief
    assert "Scan application form" in brief
    assert "Application activity" in brief
    assert "SQL and Power BI" in brief


def test_existing_database_is_upgraded_for_the_tracker(tmp_path):
    path = tmp_path / "old.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE job_matches (external_id TEXT PRIMARY KEY)")
    with initialise_database(path) as connection:
        fields = {row[1] for row in connection.execute("PRAGMA table_info(job_matches)")}
    assert {"workflow_status", "notes", "first_seen_at", "last_seen_at", "is_active", "applied_at", "updated_at"}.issubset(fields)


def test_refresh_preserves_first_seen_and_marks_missing_jobs_inactive(tmp_path):
    database = initialise_database(tmp_path / "jobs.sqlite3")
    job = Job("job-1", "Data Analyst", "Example", "Sydney", "Lever", "https://example.invalid", "SQL")
    result = score_job(job, RISHI_PROFILE)
    save_match(database, job, result)
    database.execute("UPDATE job_matches SET first_seen_at = '2026-01-01 00:00:00', last_seen_at = '2026-01-01 00:00:00'")
    database.commit()
    save_match(database, job, result)
    refreshed = get_match(database, "job-1")
    assert refreshed["first_seen_at"] == "2026-01-01 00:00:00"
    assert refreshed["last_seen_at"] != "2026-01-01 00:00:00"
    mark_company_jobs_inactive(database, "Example", [])
    assert get_match(database, "job-1")["is_active"] == 0


def test_repeated_listing_is_collapsed_and_reported(tmp_path):
    database = initialise_database(tmp_path / "jobs.sqlite3")
    first = Job("lever:1", "Data Analyst", "Example", "Sydney, NSW", "Lever", "https://one.invalid", "SQL")
    second = Job("greenhouse:2", "Data Analyst", "Example", "Sydney NSW", "Greenhouse", "https://two.invalid", "SQL")
    save_match(database, first, score_job(first, RISHI_PROFILE))
    save_match(database, second, score_job(second, RISHI_PROFILE))
    rows = list_matches(database)
    assert len(rows) == 1
    assert rows[0]["duplicate_count"] == 2
    assert len(list_matches(database, include_duplicates=True)) == 2


def test_application_timestamp_and_funnel_are_recorded(tmp_path):
    path = tmp_path / "jobs.sqlite3"
    database = initialise_database(path)
    job = Job("job-1", "Data Analyst", "Example", "Sydney", "Lever", "https://example.invalid", "SQL")
    save_match(database, job, score_job(job, RISHI_PROFILE))
    update_workflow(database, "job-1", "Applied", "Submitted on employer site")
    assert get_match(database, "job-1")["applied_at"]
    assert list_application_events(database, "job-1")[0]["status"] == "Applied"
    page = build_page(path)
    assert "Applications submitted" in page
    assert "Listing no longer active" not in page
    mark_company_jobs_inactive(database, "Example", [])
    assert "Listing no longer active" in build_page(path)


def test_supported_route_offers_supervised_browser_assistance(tmp_path):
    path = tmp_path / "project" / "data" / "jobs.sqlite3"
    database = initialise_database(path)
    job = Job("lever:example:1", "Data Analyst", "Example", "Sydney", "Lever", "https://jobs.lever.co/example/1", "SQL")
    save_match(database, job, score_job(job, RISHI_PROFILE))
    with patch("applicant_zero.dashboard.browser_setup_issue", return_value=""):
        brief = build_brief_page(path, job.external_id)
    assert "Lever" in brief
    assert "Browser assistance ready" in brief
    assert "Open assisted application" in brief


def test_private_answers_page_can_be_opened_without_showing_contact_values(tmp_path):
    project = tmp_path / "project"
    private = project / "private"
    private.mkdir(parents=True)
    resumes = {}
    for family in ("data_bi", "power_bi", "business_analysis"):
        resume = private / f"{family}.pdf"
        resume.write_text("resume", encoding="utf-8")
        resumes[family] = str(resume)
    (private / "candidate_profile.json").write_text(json.dumps({
        "contact": {"legal_name": "Rishi", "email": "private@example.com", "phone": "0400000000", "current_location": "Sydney"},
        "availability": {"full_time_from": "2026-11-15"},
        "eligibility": {"current_work_rights": "Verified", "requires_sponsorship_answer": "No"},
        "resumes": resumes,
    }), encoding="utf-8")
    page = build_answers_page(project / "data" / "jobs.sqlite3")
    assert "Reusable application answers" in page
    assert "Salary expectations" in page
    assert "private@example.com" not in page
