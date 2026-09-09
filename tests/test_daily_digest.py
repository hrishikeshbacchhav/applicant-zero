from applicant_zero.daily_digest import create_daily_digest
from applicant_zero.profile import RISHI_PROFILE
from applicant_zero.scoring import Job, score_job
from applicant_zero.storage import initialise_database, record_refresh_run, save_match, update_workflow


def test_daily_digest_groups_priority_and_follow_up_roles(tmp_path):
    database_path = tmp_path / "project" / "data" / "jobs.sqlite3"
    database = initialise_database(database_path)
    priority = Job("job-1", "Data Analyst", "Example", "Sydney", "Lever", "https://example.invalid/1", "SQL and Power BI")
    follow_up = Job("job-2", "Business Analyst", "Other", "Sydney", "Lever", "https://example.invalid/2", "requirements stakeholder")
    save_match(database, priority, score_job(priority, RISHI_PROFILE))
    save_match(database, follow_up, score_job(follow_up, RISHI_PROFILE))
    update_workflow(database, "job-2", "Applied", "Submitted")
    record_refresh_run(database, "Daily discovery refresh", 2, 2, detail="2 company boards checked")
    output = create_daily_digest(database_path)
    page = output.read_text(encoding="utf-8")
    assert "New roles worth reviewing" in page
    assert "Follow-ups" in page
    assert "Data Analyst" in page
    assert "Business Analyst" in page
