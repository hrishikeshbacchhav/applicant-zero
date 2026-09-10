from applicant_zero.profile import RISHI_PROFILE
from applicant_zero.reporting import outcome_summary, tracker_csv
from applicant_zero.scoring import Job, score_job
from applicant_zero.storage import initialise_database, save_match, save_submission_proof, update_workflow


def test_tracker_export_contains_job_status_and_followup(tmp_path):
    database_path = tmp_path / "jobs.sqlite3"
    database = initialise_database(database_path)
    job = Job("job-1", "Data Analyst", "Example", "Sydney", "Lever", "https://example.invalid", "SQL and Power BI")
    save_match(database, job, score_job(job, RISHI_PROFILE))
    save_submission_proof(database, job.external_id, "Confirmation", "", "Submitted")
    update_workflow(database, job.external_id, "Applied", "Submitted")
    export = tracker_csv(database_path)
    assert "tracker_status" in export
    assert "Data Analyst" in export
    assert "Applied" in export
    assert "Due" in export


def test_outcome_summary_reports_submissions_and_interviews(tmp_path):
    database_path = tmp_path / "jobs.sqlite3"
    database = initialise_database(database_path)
    applied = Job("applied", "Data Analyst", "Example", "Sydney", "Lever", "https://example.invalid/a", "SQL and Power BI")
    interview = Job("interview", "Power BI Analyst", "Example", "Sydney", "Lever", "https://example.invalid/b", "Power BI and DAX")
    save_match(database, applied, score_job(applied, RISHI_PROFILE))
    save_match(database, interview, score_job(interview, RISHI_PROFILE))
    update_workflow(database, applied.external_id, "Applied", "Submitted")
    update_workflow(database, interview.external_id, "Interview", "Interview booked")
    summary = outcome_summary(database_path)
    assert summary["submitted"] == 2
    assert summary["interviews"] == 1
    assert summary["interview_rate"] == 50.0


def test_outcome_summary_keeps_offers_and_rejections_separate(tmp_path):
    database_path = tmp_path / "jobs.sqlite3"
    database = initialise_database(database_path)
    offer = Job("offer", "Data Analyst", "Example", "Sydney", "Lever", "https://example.invalid/o", "SQL and Power BI")
    rejected = Job("rejected", "Data Analyst", "Example", "Sydney", "Lever", "https://example.invalid/r", "SQL and Power BI")
    save_match(database, offer, score_job(offer, RISHI_PROFILE))
    save_match(database, rejected, score_job(rejected, RISHI_PROFILE))
    update_workflow(database, offer.external_id, "Offer", "Offer received")
    update_workflow(database, rejected.external_id, "Rejected", "Employer decision recorded")
    summary = outcome_summary(database_path)
    assert summary["offers"] == 1
    assert summary["rejected"] == 1
    assert summary["response_rate"] == 50.0
