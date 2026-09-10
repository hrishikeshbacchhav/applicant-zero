from unittest.mock import patch

import json

from applicant_zero.sources.company_boards import _ashby_jobs, _get_json, _greenhouse_jobs, _lever_jobs, _smartrecruiters_jobs, fetch_company_boards_with_report
from applicant_zero.storage import initialise_database, list_board_checks, list_board_check_trends, save_board_checks


def test_greenhouse_mapping():
    payload = {"jobs": [{"id": 7, "title": "Data Analyst", "location": {"name": "Sydney, NSW"}, "absolute_url": "https://example.invalid", "content": "SQL and Power BI"}]}
    with patch("applicant_zero.sources.company_boards._get_json", return_value=payload):
        jobs = _greenhouse_jobs("Example", "token")
    assert jobs[0].external_id == "greenhouse:token:7"
    assert jobs[0].location == "Sydney, NSW"


def test_public_feed_requests_identify_the_private_discovery_client(monkeypatch):
    seen = {}
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self): return b'{}'
    def fake_open(request, timeout):
        seen["agent"] = request.get_header("User-agent")
        return Response()
    monkeypatch.setattr("applicant_zero.sources.company_boards.urlopen", fake_open)
    assert _get_json("https://example.invalid") == {}
    assert "Applicant-Zero" in seen["agent"]


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


def test_smartrecruiters_mapping_reads_public_listing_and_detail():
    listing = {"content": [{"id": "42", "name": "IT Support Officer", "location": {"city": "Sydney", "region": "NSW", "country": "Australia"}}]}
    detail = {"applyUrl": "https://jobs.smartrecruiters.com/example/42", "jobAd": {"sections": {"jobDescription": {"text": "Provide technical support and resolve service desk incidents."}}}}
    with patch("applicant_zero.sources.company_boards._get_json", side_effect=[listing, detail]):
        jobs = _smartrecruiters_jobs("Example", "Example")
    assert jobs[0].external_id == "smartrecruiters:Example:42"
    assert jobs[0].location == "Sydney, NSW, Australia"
    assert "technical support" in jobs[0].description


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


def test_parallel_board_collection_keeps_configured_order(tmp_path):
    path = tmp_path / "boards.json"
    path.write_text(json.dumps([
        {"company": "First", "ats": "lever", "token": "first"},
        {"company": "Second", "ats": "lever", "token": "second"},
    ]), encoding="utf-8")
    with patch("applicant_zero.sources.company_boards._lever_jobs", return_value=[]):
        _, reports = fetch_company_boards_with_report(path)
    assert [report.company for report in reports] == ["First", "Second"]


def test_board_health_is_saved_locally(tmp_path):
    database = initialise_database(tmp_path / "jobs.sqlite3")
    save_board_checks(database, [type("Report", (), {"company": "Example", "status": "checked", "job_count": 3, "message": ""})()])
    rows = list_board_checks(database)
    assert rows[0]["company"] == "Example"
    assert rows[0]["job_count"] == 3


def test_board_check_history_keeps_a_listing_change_without_confusing_unavailable_with_zero(tmp_path):
    database = initialise_database(tmp_path / "jobs.sqlite3")
    report = lambda status, count: type("Report", (), {"company": "Example", "status": status, "job_count": count, "message": "endpoint issue" if status == "unavailable" else ""})()
    save_board_checks(database, [report("checked", 5)])
    save_board_checks(database, [report("checked", 3)])
    trends, history = list_board_check_trends(database)

    assert trends["example"]["job_count"] == 3
    assert trends["example"]["change"] == -2
    assert len(history) == 2

    save_board_checks(database, [report("unavailable", 0)])
    trends, _ = list_board_check_trends(database)
    assert trends["example"]["status"] == "unavailable"
    assert trends["example"]["change"] is None


def test_invalid_or_duplicate_board_config_does_not_stop_valid_collection(tmp_path):
    path = tmp_path / "boards.json"
    path.write_text(json.dumps([
        {"company": "Valid", "ats": "lever", "token": "valid"},
        {"company": "Duplicate", "ats": "lever", "token": "valid"},
        {"company": "Broken", "ats": "unknown", "token": "broken"},
    ]), encoding="utf-8")
    with patch("applicant_zero.sources.company_boards._lever_jobs", return_value=[]):
        _, reports = fetch_company_boards_with_report(path)
    assert [report.company for report in reports] == ["Duplicate", "Broken", "Valid"]
    assert [report.status for report in reports] == ["unavailable", "unavailable", "checked"]


def test_smartrecruiters_board_is_an_accepted_public_board_type(tmp_path):
    path = tmp_path / "boards.json"
    path.write_text(json.dumps([{"company": "Example", "ats": "smartrecruiters", "token": "Example"}]), encoding="utf-8")
    with patch("applicant_zero.sources.company_boards._smartrecruiters_jobs", return_value=[]):
        _, reports = fetch_company_boards_with_report(path)
    assert reports[0].status == "checked"
