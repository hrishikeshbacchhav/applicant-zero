import json
from unittest.mock import MagicMock, patch

from applicant_zero.application_answers import advertised_salary_range, ensure_answer_library, salary_expectation_for_job
from applicant_zero.application_routes import ApplicationRoute, classify_application_url, inspect_application_route, supports_supervised_browser_handoff
from applicant_zero.storage import (
    get_application_route,
    initialise_database,
    list_application_events,
    log_application_event,
    save_application_route,
)


def test_known_application_platforms_are_classified():
    lever = classify_application_url("https://jobs.lever.co/example/abc")
    assert lever.platform == "Lever"
    assert lever.support_level == "assisted"
    assert lever.apply_url == "https://jobs.lever.co/example/abc/apply"

    greenhouse = classify_application_url("https://job-boards.greenhouse.io/example/jobs/123")
    assert greenhouse.platform == "Greenhouse"
    assert greenhouse.support_level == "pilot"

    workday = classify_application_url("https://example.wd3.myworkdayjobs.com/en-US/jobs/job/123")
    assert workday.platform == "Workday"
    assert workday.account_required is True
    assert workday.support_level == "complex"
    assert supports_supervised_browser_handoff(workday) is True
    assert supports_supervised_browser_handoff(classify_application_url("https://www.seek.com.au/job/123")) is True
    assert supports_supervised_browser_handoff(classify_application_url("https://example.com/jobs/123")) is False


def test_form_scan_counts_fields_and_detects_captcha():
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b"""
        <form><input name='name' required><input type='hidden' name='token'>
        <input type='file' name='resume' required><select name='country' required></select>
        <textarea name='answer'></textarea><div class='g-recaptcha'></div></form>
    """
    with patch("applicant_zero.application_routes.urlopen", return_value=response):
        route = inspect_application_route("https://jobs.lever.co/example/abc")
    assert route.field_count == 4
    assert route.required_field_count == 3
    assert route.captcha_detected is True


def test_route_and_application_events_are_saved(tmp_path):
    database = initialise_database(tmp_path / "jobs.sqlite3")
    route = ApplicationRoute("Lever", "assisted", "https://jobs.lever.co/example/abc/apply", field_count=5, required_field_count=3)
    save_application_route(database, "job-1", route)
    log_application_event(database, "job-1", "route_check", "completed", "Five fields detected")
    assert get_application_route(database, "job-1")["field_count"] == 5
    events = list_application_events(database, "job-1")
    assert events[0]["status"] == "completed"


def test_answer_library_uses_profile_and_preserves_confirmed_answers(tmp_path):
    private = tmp_path / "private"
    private.mkdir()
    path = private / "application_answers.json"
    path.write_text(json.dumps({
        "verified_answers": {},
        "answers_requiring_confirmation": {"salary_expectations": "AUD 80,000 plus super"},
    }), encoding="utf-8")
    profile = {
        "contact": {"legal_name": "Rishi Example", "email": "rishi@example.com", "phone": "0400000000", "current_location": "Sydney"},
        "availability": {"full_time_from": "2026-11-15"},
        "eligibility": {"current_work_rights": "Verified current status", "requires_sponsorship_answer": "No"},
    }
    library = ensure_answer_library(tmp_path, profile)
    assert library["verified_answers"]["full_name"] == "Rishi Example"
    assert library["answers_requiring_confirmation"]["salary_expectations"] == "AUD 80,000 plus super"
    assert path.exists()


def test_salary_guidance_uses_a_clearly_advertised_range_first():
    job = {"description": "The salary is $90,000 - $110,000 plus super."}
    answers = {"answers_requiring_confirmation": {"salary_expectations": "AUD 95,000 plus super"}}
    assert advertised_salary_range(job["description"]) == (90_000, 110_000)
    assert salary_expectation_for_job(job, answers) == "AUD 100,000 base salary plus superannuation (negotiable)"
