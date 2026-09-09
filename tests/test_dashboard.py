from applicant_zero.dashboard import build_actions_page, build_answers_page, build_brief_page, build_outcomes_page, build_page, build_resume_copy_page, build_session_trace_page
from applicant_zero.manual_import import import_listing, source_name
from applicant_zero.resume_review import create_resume_review, load_resume_review
from applicant_zero.application_readiness import evaluate_application_readiness
from applicant_zero.profile import RISHI_PROFILE
from applicant_zero.scoring import Job, score_job
import json
import sqlite3
from unittest.mock import patch

from applicant_zero.storage import (
    get_match,
    get_material_review,
    get_submission_proof,
    get_followup,
    initialise_database,
    list_application_events,
    list_matches,
    mark_company_jobs_inactive,
    save_match,
    save_material_review,
    save_submission_proof,
    complete_followup,
    complete_manual_action,
    list_manual_actions,
    record_refresh_run,
    update_workflow,
    save_manual_action,
)


def test_empty_dashboard_has_guidance(tmp_path):
    page = build_page(tmp_path / "missing.sqlite3")
    assert "No jobs collected yet" in page
    assert "Add a job from another website" in page
    assert "Focus for today" in page
    outcomes = build_outcomes_page(tmp_path / "missing.sqlite3")
    assert "Search progress" in outcomes
    assert "Applications submitted" in outcomes


def test_application_answers_page_offers_private_resume_evidence_inventory(tmp_path):
    private = tmp_path / "private"
    private.mkdir()
    resumes = {}
    for family in ("data_bi", "power_bi", "business_analysis"):
        path = private / f"{family}.pdf"
        path.write_bytes(b"placeholder")
        resumes[family] = str(path)
    (private / "candidate_profile.json").write_text(json.dumps({
        "contact": {"legal_name": "Rishi", "email": "r@example.com", "phone": "0400", "current_location": "Sydney"},
        "availability": {"full_time_from": "2026-11-15"},
        "eligibility": {"current_work_rights": "Verified", "requires_sponsorship_answer": "No"},
        "resumes": resumes,
    }), encoding="utf-8")
    page = build_answers_page(tmp_path / "data" / "jobs.sqlite3")
    assert "Approved résumé evidence" in page
    assert "Refresh résumé evidence inventory" in page


def test_manual_action_queue_persists_and_can_be_completed(tmp_path):
    path = tmp_path / "jobs.sqlite3"
    database = initialise_database(path)
    save_manual_action(database, "job-1", "captcha", "Complete CAPTCHA", "Complete the employer CAPTCHA, then resume the application.")
    assert len(list_manual_actions(database)) == 1
    assert "Complete CAPTCHA" in build_actions_page(path)
    action_id = list_manual_actions(database)[0]["id"]
    complete_manual_action(database, action_id)
    assert list_manual_actions(database) == []


def test_manual_action_queue_deduplicates_an_open_handoff(tmp_path):
    database = initialise_database(tmp_path / "jobs.sqlite3")
    save_manual_action(database, "job-1", "captcha", "Complete CAPTCHA", "Complete it in the browser.")
    save_manual_action(database, "job-1", "captcha", "Complete CAPTCHA", "Same browser action repeated.")
    assert len(list_manual_actions(database)) == 1


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
    assert "Start with the actions most likely" in page
    assert "Current listings" in page
    assert "Live sources" in page
    assert "Search role, company or location" in page
    assert "All companies" in page
    assert "All tracker stages" in page
    assert "All role lanes" in page
    assert "All relevant" in page
    assert "Current relevant listings" in page
    assert "Preparing" in page
    brief = build_brief_page(tmp_path / "jobs.sqlite3", "job-1")
    assert "Before applying" in brief
    assert "Application compatibility" in brief
    assert "Application readiness" in brief
    assert "Create editable role copy" in brief
    assert "Record employer confirmation and mark Applied" in brief
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


def test_browser_trace_page_is_private_and_linked_from_brief(tmp_path):
    path = tmp_path / "project" / "data" / "jobs.sqlite3"
    database = initialise_database(path)
    job = Job("lever:example:1", "Data Analyst", "Example", "Sydney", "Lever", "https://jobs.lever.co/example/1", "SQL")
    save_match(database, job, score_job(job, RISHI_PROFILE))
    from applicant_zero.session_trace import append_trace, start_trace
    start_trace(path, job.external_id, "Lever", "https://jobs.lever.co/example/1/apply")
    append_trace(path, job.external_id, "required_question", "Review a required question.")
    from applicant_zero.session_trace import record_form_inventory
    record_form_inventory(path, job.external_id, "https://jobs.lever.co/example/1/apply", [{"label": "Email", "control": "email", "required": True, "handling": "recognised"}])
    assert "View browser session trace" in build_brief_page(path, job.external_id)
    trace_page = build_session_trace_page(path, job.external_id)
    assert "Browser session trace" in trace_page
    assert "Review a required question." in trace_page
    assert "Form page inventory" in trace_page


def test_login_required_route_offers_supervised_handoff(tmp_path):
    path = tmp_path / "project" / "data" / "jobs.sqlite3"
    database = initialise_database(path)
    job = Job("seek:example:1", "Data Analyst", "Example", "Sydney", "SEEK", "https://www.seek.com.au/job/123", "SQL")
    save_match(database, job, score_job(job, RISHI_PROFILE))
    with patch("applicant_zero.dashboard.browser_setup_issue", return_value=""):
        brief = build_brief_page(path, job.external_id)
    assert "Open supervised login handoff" in brief


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
        "editable_resume_masters": {"data_bi": str(private / "data_bi_master.docx")},
    }), encoding="utf-8")
    (private / "data_bi_master.docx").write_text("master", encoding="utf-8")
    page = build_answers_page(project / "data" / "jobs.sqlite3")
    assert "Reusable application answers" in page
    assert "Salary expectations" in page
    assert "private@example.com" not in page


def test_imported_listing_is_scored_and_has_a_stable_source_label(tmp_path):
    database = initialise_database(tmp_path / "jobs.sqlite3")
    job = import_listing(
        database,
        RISHI_PROFILE,
        title="Data Analyst",
        company="Example Analytics",
        location="Sydney, NSW",
        url="https://www.seek.com.au/job/123456",
        description="Use SQL and Power BI to develop reports, improve data quality and work with stakeholders across the business.",
    )
    stored = get_match(database, job.external_id)
    assert stored["source"] == "Imported · SEEK"
    assert stored["recommendation"] in {"Strong apply", "Apply", "Review"}
    assert source_name("https://www.linkedin.com/jobs/view/123") == "Imported · LinkedIn"


def test_resume_review_stays_private_and_uses_the_saved_ai_draft(tmp_path):
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
        "editable_resume_masters": {"data_bi": str(private / "data_bi_master.docx")},
    }), encoding="utf-8")
    (private / "data_bi_master.docx").write_text("master", encoding="utf-8")
    database_path = project / "data" / "jobs.sqlite3"
    database = initialise_database(database_path)
    job = Job("job-1", "Data Analyst", "Example", "Sydney", "test", "https://example.invalid", "SQL and Power BI")
    save_match(database, job, score_job(job, RISHI_PROFILE))
    packet_dir = private / "application_packets"
    packet_dir.mkdir()
    (packet_dir / "example-data-analyst-ai-draft.json").write_text(json.dumps({
        "draft": {"resume_summary": "Truthful summary", "resume_bullet_suggestions": ["Use SQL evidence"], "unsupported_requirements": [], "questions_to_confirm": []}
    }), encoding="utf-8")
    output = create_resume_review(project / "data" / "jobs.sqlite3", "job-1")
    assert output.exists()
    review = load_resume_review(project / "data" / "jobs.sqlite3", "job-1")
    assert "Tailored résumé editing pack" in review
    assert "Truthful summary" in review
    assert "data_bi_master.docx" in review
    assert "Quality check before use" in review


def test_editable_resume_copy_page_identifies_the_private_word_file(tmp_path):
    project = tmp_path / "project"
    private = project / "private"
    private.mkdir(parents=True)
    master = private / "data_bi_master.docx"
    master.write_text("master", encoding="utf-8")
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
        "editable_resume_masters": {"data_bi": str(master)},
    }), encoding="utf-8")
    database_path = project / "data" / "jobs.sqlite3"
    database = initialise_database(database_path)
    job = Job("job-1", "Data Analyst", "Example", "Sydney", "test", "https://example.invalid", "SQL")
    save_match(database, job, score_job(job, RISHI_PROFILE))
    from applicant_zero.resume_output import create_editable_resume_copy
    output = create_editable_resume_copy(database_path, job.external_id)
    page = build_resume_copy_page(database_path, job.external_id)
    assert "Editable role copy ready" in page
    assert output.name in page
    assert "Open or download Word copy" in page


def test_review_and_employer_confirmation_are_recorded_in_the_tracker(tmp_path):
    database = initialise_database(tmp_path / "jobs.sqlite3")
    job = Job("job-1", "Data Analyst", "Example", "Sydney", "test", "https://example.invalid", "SQL")
    save_match(database, job, score_job(job, RISHI_PROFILE))
    save_material_review(database, job.external_id, "Checked resume and cover letter")
    save_submission_proof(database, job.external_id, "Thank you email", "https://example.invalid/confirmation", "Submitted through employer site")
    update_workflow(database, job.external_id, "Applied", "Submitted through employer site")
    assert get_material_review(database, job.external_id)["materials_reviewed"] == 1
    assert get_submission_proof(database, job.external_id)["confirmation_reference"] == "Thank you email"
    assert get_followup(database, job.external_id)["status"] == "Due"
    complete_followup(database, job.external_id, "Checked in")
    assert get_followup(database, job.external_id)["status"] == "Completed"
    assert get_match(database, job.external_id)["workflow_status"] == "Applied"


def test_readiness_identifies_the_private_setup_that_is_still_missing(tmp_path):
    database = initialise_database(tmp_path / "data" / "jobs.sqlite3")
    job = Job("job-1", "Data Analyst", "Example", "Sydney", "test", "https://example.invalid", "SQL")
    save_match(database, job, score_job(job, RISHI_PROFILE))
    readiness = evaluate_application_readiness(tmp_path / "data" / "jobs.sqlite3", get_match(database, job.external_id), False)
    assert readiness[0].label == "Candidate profile"
    assert readiness[0].complete is False


def test_dashboard_shows_latest_discovery_refresh_and_new_listing_filter(tmp_path):
    database = initialise_database(tmp_path / "jobs.sqlite3")
    job = Job("job-1", "Data Analyst", "Example", "Sydney", "Lever", "https://example.invalid", "SQL")
    save_match(database, job, score_job(job, RISHI_PROFILE))
    record_refresh_run(database, "Company career boards", 12, 3, checked_count=4, unavailable_count=1, detail="4 boards checked")
    page = build_page(tmp_path / "jobs.sqlite3")
    assert "Last discovery refresh" in page
    assert "New this week" in page
    assert "source(s) unavailable" in page
    assert "Daily priorities" in page
    assert "System health" in page
    assert "4 boards checked" in page
