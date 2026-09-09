from applicant_zero.profile import RISHI_PROFILE
from applicant_zero.reporting import tracker_csv
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
