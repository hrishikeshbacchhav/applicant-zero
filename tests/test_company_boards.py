from unittest.mock import patch

import json

from applicant_zero.sources.company_boards import _ashby_jobs, _greenhouse_jobs, _lever_jobs, fetch_company_boards_with_report
from applicant_zero.storage import initialise_database, list_board_checks, save_board_checks


def test_greenhouse_mapping():
    payload = {"jobs": [{"id": 7, "title": "Data Analyst", "location": {"name": "Sydney, NSW"}, "absolute_url": "https://example.invalid", "content": "SQL and Power BI"}]}
    with patch("applicant_zero.sources.company_boards._get_json", return_value=payload):
        jobs = _greenhouse_jobs("Example", "token")
    assert jobs[0].external_id == "greenhouse:token:7"
    assert jobs[0].location == "Sydney, NSW"


def test_lever_mapping():
    payload = [{"id": "9", "text": "Business Analyst", "categories": {"location": "Sydney, NSW"}, "hostedUrl": "https://example.invalid", "descriptionPlain": "Requirements gathering"}]
    with patch("applicant_zero.sources.company_boards._get_json", return_value=payload):
        jobs = _lever_jobs("Example", "token")
    assert jobs[0].external_id == "lever:token:9"
    assert jobs[0].title == "Business Analyst"


def test_ashby_mapping_keeps_plain_description_and_salary():
    payload = {"jobs": [{"title": "Data Analyst", "location": "Sydney", "isListed": True, "applyUrl": "https://jobs.ashbyhq.com/example/apply", "descriptionPlain": "Use SQL", "compensation": {"scrapeableCompensationSalarySummary": "$80K - $90K"}}]}
    with patch("applicant_zero.sources.company_boards._get_json", return_value=payload):
        jobs = _ashby_jobs("Example", "example")
    assert jobs[0].source == "Ashby"
    assert "Compensation" in jobs[0].description


def test_one_unavailable_board_does_not_stop_other_boards(tmp_path):
    path = tmp_path / "boards.json"
    path.write_text(json.dumps([
        {"company": "Available", "ats": "lever", "token": "available"},
        {"company": "Unavailable", "ats": "lever", "token": "unavailable"},
    ]), encoding="utf-8")
    def fake_fetch(company, token):
        if token == "unavailable":
            raise OSError("network problem")
        return []
    with patch("applicant_zero.sources.company_boards._lever_jobs", side_effect=fake_fetch):
        jobs, reports = fetch_company_boards_with_report(path)
    assert jobs == []
    assert [report.status for report in reports] == ["checked", "unavailable"]


def test_board_health_is_saved_locally(tmp_path):
    database = initialise_database(tmp_path / "jobs.sqlite3")
    save_board_checks(database, [type("Report", (), {"company": "Example", "status": "checked", "job_count": 3, "message": ""})()])
    rows = list_board_checks(database)
    assert rows[0]["company"] == "Example"
    assert rows[0]["job_count"] == 3
