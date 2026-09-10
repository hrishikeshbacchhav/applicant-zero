from applicant_zero.gmail_sync import classify_job_message, gmail_setup_status
from applicant_zero.storage import (
    initialise_database,
    latest_email_sync_run,
    list_email_events,
    record_email_sync_run,
    save_email_event,
)


def test_job_confirmation_matches_only_a_clear_company_signal():
    jobs = [
        {"external_id": "job-1", "company": "Harbour Insights", "title": "Data Analyst"},
        {"external_id": "job-2", "company": "Other Company", "title": "Business Analyst"},
    ]
    result = classify_job_message(
        "Your application has been received",
        "careers@harbourinsights.com",
        "Thank you for applying for the Data Analyst role at Harbour Insights.",
        jobs,
    )

    assert result.category == "application confirmation"
    assert result.external_id == "job-1"
    assert result.confidence == "high"
    assert result.target_status == "Applied"


def test_unmatched_or_ambiguous_messages_do_not_update_a_tracker_role():
    jobs = [
        {"external_id": "one", "company": "Example", "title": "Data Analyst"},
        {"external_id": "two", "company": "Example", "title": "Business Analyst"},
    ]
    result = classify_job_message("We received your application", "jobs@example.com", "Thanks for applying at Example.", jobs)

    assert result.external_id is None
    assert result.confidence == "ambiguous"
    assert result.target_status is None


def test_email_storage_keeps_metadata_and_sync_summary_only(tmp_path):
    database = initialise_database(tmp_path / "jobs.sqlite3")
    assert save_email_event(database, "message-1", "123", "jobs@example.com", "Application received", "application confirmation", None, "unmatched", False)
    assert not save_email_event(database, "message-1", "123", "jobs@example.com", "Application received", "application confirmation", None, "unmatched", False)
    record_email_sync_run(database, 1, 0, 0, "Read-only check")

    assert list_email_events(database)[0]["subject"] == "Application received"
    assert latest_email_sync_run(database)["detail"] == "Read-only check"


def test_gmail_setup_status_requires_a_private_oauth_file(tmp_path):
    connected, detail = gmail_setup_status(tmp_path)

    assert not connected
    assert "Not connected" in detail
