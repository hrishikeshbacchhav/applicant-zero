from unittest.mock import patch

import json
import sqlite3

from applicant_zero.scoring import Job
from datetime import date

from applicant_zero.sources.company_boards import _ashby_jobs, _get_json, _greenhouse_jobs, _lever_jobs, _needs_candidate_detail, _recruitee_jobs, _request_count_for_board, _smartrecruiters_jobs, _workable_jobs, _workday_jobs, _workday_search_terms, fetch_company_boards_with_report
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


def test_smartrecruiters_mapping_pages_a_large_public_board_with_a_bounded_cap():
    first = [{"id": str(index), "name": f"Role {index}", "location": {"city": "Sydney"}} for index in range(100)]
    second = [{"id": "101", "name": "Role 101", "location": {"city": "Sydney"}}]
    listing_first = {"totalFound": 101, "content": first}
    listing_second = {"totalFound": 101, "content": second}
    with patch("applicant_zero.sources.company_boards._get_json", side_effect=[listing_first, listing_second]) as get:
        jobs = _smartrecruiters_jobs("Example", "Example")
    assert len(jobs) == 101
    assert "offset=0" in get.call_args_list[0].args[0]
    assert "offset=100" in get.call_args_list[1].args[0]
    assert get.call_count == 2


def test_smartrecruiters_details_are_limited_to_candidate_lane_titles():
    listing = {"content": [
        {"id": str(index), "name": "IT Support Analyst", "location": {"city": "Sydney"}}
        for index in range(20)
    ]}
    detail = {"jobAd": {"sections": {"jobDescription": {"text": "Support detail"}}}}
    with patch("applicant_zero.sources.company_boards._get_json", side_effect=[listing, *([detail] * 12)]) as get:
        jobs = _smartrecruiters_jobs("Example", "Example")
    assert len(jobs) == 20
    assert get.call_count == 13


def test_smartrecruiters_prioritises_sydney_detail_before_generic_australia_matches():
    listing = {"content": [
        {"id": str(index), "name": "Data Analyst", "location": {"country": "Australia"}}
        for index in range(12)
    ] + [{"id": "sydney", "name": "Data Analyst", "location": {"city": "Sydney", "country": "Australia"}}]}
    with patch("applicant_zero.sources.company_boards._get_json", side_effect=[listing, *([{ "jobAd": {} }] * 12)]) as get:
        _smartrecruiters_jobs("Example", "Example")
    detail_urls = [call.args[0] for call in get.call_args_list[1:]]
    assert any(url.endswith("/sydney") for url in detail_urls)


def test_workday_prioritises_sydney_detail_before_generic_australia_matches():
    generic = [
        {"title": "Data Analyst", "externalPath": f"/job/generic-{index}", "locationsText": "Australia"}
        for index in range(12)
    ]
    local = {"title": "Data Analyst", "externalPath": "/job/sydney", "locationsText": "Sydney, NSW, Australia"}
    with patch("applicant_zero.sources.company_boards._post_json", return_value={"total": 13, "jobPostings": [*generic, local]}), patch(
        "applicant_zero.sources.company_boards._get_json", return_value={"jobPostingInfo": {}}
    ) as get:
        _workday_jobs("Example", "example.wd3.myworkdayjobs.com/Careers")
    detail_urls = [call.args[0] for call in get.call_args_list]
    assert any(url.endswith("/job/sydney") for url in detail_urls)


def test_candidate_detail_read_keeps_local_and_generic_australian_roles_only():
    assert _needs_candidate_detail("Data Analyst", "Sydney, NSW, Australia")
    assert _needs_candidate_detail("Data Analyst", "Australia")
    assert _needs_candidate_detail("Data Analyst", "Unknown location")
    assert not _needs_candidate_detail("Data Analyst", "London, England")
    assert not _needs_candidate_detail("Unrelated role", "Sydney, NSW")


def test_candidate_detail_read_recognises_extended_sydney_employment_centres():
    assert _needs_candidate_detail("Data Analyst", "Wetherill Park, NSW, Australia")
    assert _needs_candidate_detail("IT Support Analyst", "Hurstville")


def test_candidate_detail_read_does_not_spend_local_budget_on_ambiguous_overseas_places():
    assert not _needs_candidate_detail("Data Analyst", "Liverpool, England, United Kingdom")
    assert not _needs_candidate_detail("IT Support Analyst", "Penrith, England")
    assert _needs_candidate_detail("Data Analyst", "Liverpool, NSW, Australia")


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


def test_board_health_keeps_separate_public_boards_for_the_same_employer(tmp_path):
    database = initialise_database(tmp_path / "jobs.sqlite3")
    reports = [
        type("Report", (), {"company": "Example", "status": "checked", "job_count": 3, "message": "", "ats": "workday", "token": "example.wd1.myworkdayjobs.com/Careers"})(),
        type("Report", (), {"company": "Example", "status": "unavailable", "job_count": 0, "message": "endpoint unavailable", "ats": "workday", "token": "example.wd5.myworkdayjobs.com/Careers"})(),
    ]
    save_board_checks(database, reports)

    rows = list_board_checks(database)
    trends, history = list_board_check_trends(database)

    assert len(rows) == 2
    assert {row["board_key"] for row in rows} == {
        "workday:example.wd1.myworkdayjobs.com/careers",
        "workday:example.wd5.myworkdayjobs.com/careers",
    }
    assert trends["workday:example.wd1.myworkdayjobs.com/careers"]["job_count"] == 3
    assert trends["workday:example.wd5.myworkdayjobs.com/careers"]["status"] == "unavailable"
    assert len(history) == 2


def test_old_company_only_board_health_database_is_migrated_without_losing_the_check(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE board_checks (company TEXT PRIMARY KEY, status TEXT NOT NULL, job_count INTEGER NOT NULL, detail TEXT NOT NULL DEFAULT '', checked_at TEXT NOT NULL)")
        connection.execute("CREATE TABLE board_check_history (id INTEGER PRIMARY KEY AUTOINCREMENT, company TEXT NOT NULL, status TEXT NOT NULL, job_count INTEGER NOT NULL, detail TEXT NOT NULL DEFAULT '', checked_at TEXT NOT NULL)")
        connection.execute("INSERT INTO board_checks VALUES ('Legacy', 'checked', 4, '', '2026-01-01 00:00:00')")
        connection.execute("INSERT INTO board_check_history (company, status, job_count, detail, checked_at) VALUES ('Legacy', 'checked', 4, '', '2026-01-01 00:00:00')")

    database = initialise_database(path)
    rows = list_board_checks(database)
    _, history = list_board_check_trends(database)

    assert rows[0]["board_key"] == "legacy"
    assert history[0]["board_key"] == "legacy"


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


def test_workable_mapping_uses_the_public_careers_payload():
    payload = {"jobs": [{
        "title": "IT Support Officer", "shortcode": "ABC123", "url": "https://apply.workable.com/j/ABC123",
        "city": "Sydney", "state": "New South Wales", "country": "Australia",
        "employment_type": "Full-time", "experience": "Entry level", "description": "<p>Helpdesk support</p>",
    }]}
    with patch("applicant_zero.sources.company_boards._get_json", return_value=payload):
        jobs = _workable_jobs("Example", "example")
    assert jobs[0].external_id == "workable:example:ABC123"
    assert jobs[0].source == "Workable"
    assert "Full-time" in jobs[0].description


def test_workable_board_is_an_accepted_public_board_type(tmp_path):
    path = tmp_path / "boards.json"
    path.write_text(json.dumps([{"company": "Example", "ats": "workable", "token": "example"}]), encoding="utf-8")
    with patch("applicant_zero.sources.company_boards._workable_jobs", return_value=[]):
        _, reports = fetch_company_boards_with_report(path)
    assert reports[0].status == "checked"


def test_recruitee_mapping_keeps_only_published_jobs():
    payload = {"offers": [
        {"id": "published", "title": "Data Analyst", "status": "published", "careers_url": "https://example.recruitee.com/o/data", "description": "SQL", "locations": [{"name": "Sydney"}]},
        {"id": "draft", "title": "Draft role", "status": "draft"},
    ]}
    with patch("applicant_zero.sources.company_boards._get_json", return_value=payload):
        jobs = _recruitee_jobs("Example", "example")
    assert [(job.external_id, job.location) for job in jobs] == [("recruitee:example:published", "Sydney")]


def test_recruitee_board_is_an_accepted_public_board_type(tmp_path):
    path = tmp_path / "boards.json"
    path.write_text(json.dumps([{ "company": "Example", "ats": "recruitee", "token": "example" }]), encoding="utf-8")
    with patch("applicant_zero.sources.company_boards._recruitee_jobs", return_value=[]):
        _, reports = fetch_company_boards_with_report(path)
    assert reports[0].status == "checked"


def test_workday_mapping_reads_the_public_careers_search_response():
    payload = {"jobPostings": [{
        "title": "Service Desk Analyst", "externalPath": "/en-US/Careers/job/Sydney/Service-Desk-Analyst_123",
        "locationsText": "Sydney, NSW, Australia", "postedOn": "Posted Today", "timeType": "Full time",
    }]}
    detail = {"jobPostingInfo": {"jobDescription": "Resolve service desk requests.", "timeType": "Full time"}}
    with patch("applicant_zero.sources.company_boards._post_json", return_value=payload) as post, patch(
        "applicant_zero.sources.company_boards._get_json", return_value=detail
    ) as get:
        jobs = _workday_jobs("Example", "example.wd3.myworkdayjobs.com/Careers")
    assert jobs[0].external_id.startswith("workday:example.wd3.myworkdayjobs.com:Careers:")
    assert jobs[0].url.endswith("Service-Desk-Analyst_123")
    assert "Published: Posted Today" in jobs[0].description
    assert post.call_args.args[0].endswith("/wday/cxs/example/Careers/jobs")
    assert post.call_args.args[1] == {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}
    assert get.call_args.args[0].endswith("/wday/cxs/example/Careers/job/Sydney/Service-Desk-Analyst_123")
    assert "Resolve service desk requests" in jobs[0].description


def test_workday_mapping_pages_a_large_public_board_with_a_bounded_cap():
    first = [{"title": f"Role {index}", "externalPath": f"/job/{index}", "locationsText": "Sydney"} for index in range(20)]
    data = [{"title": "Data Analyst", "externalPath": "/job/data", "locationsText": "Sydney"}]
    analyst = [{"title": "Business Analyst", "externalPath": "/job/business", "locationsText": "Sydney"}]
    support = [{"title": "Support Analyst", "externalPath": "/job/support", "locationsText": "Sydney"}]
    admin = [{"title": "Administration Officer", "externalPath": "/job/admin", "locationsText": "Sydney"}]
    with patch("applicant_zero.sources.company_boards._workday_search_terms", return_value=("", "sydney", "data", "analyst", "support")), patch(
        "applicant_zero.sources.company_boards._post_json", side_effect=[
            {"total": 21, "jobPostings": first}, {"jobPostings": data}, {"jobPostings": analyst},
            {"jobPostings": support}, {"jobPostings": admin},
        ]
    ) as post:
        jobs = _workday_jobs("Example", "example.wd3.myworkdayjobs.com/Careers")
    assert len(jobs) == 24
    assert [call.args[1]["searchText"] for call in post.call_args_list] == ["", "sydney", "data", "analyst", "support"]


def test_workday_mapping_deduplicates_overlapping_targeted_search_results():
    first = [{"title": f"Role {index}", "externalPath": f"/job/{index}", "locationsText": "Sydney"} for index in range(20)]
    overlapping = {"title": "Business Data Analyst", "externalPath": "/job/analyst", "locationsText": "Sydney"}
    with patch("applicant_zero.sources.company_boards._post_json", side_effect=[
        {"total": 21, "jobPostings": first}, {"jobPostings": [overlapping]}, {"jobPostings": [overlapping]},
        {"jobPostings": []}, {"jobPostings": []},
    ]):
        jobs = _workday_jobs("Example", "example.wd3.myworkdayjobs.com/Careers")
    assert [job.external_id for job in jobs].count("workday:example.wd3.myworkdayjobs.com:Careers:/job/analyst") == 1


def test_workday_details_are_limited_to_candidate_lane_titles():
    first = [
        {"title": "IT Support Analyst", "externalPath": f"/job/{index}", "locationsText": "Sydney"}
        for index in range(20)
    ]
    with patch("applicant_zero.sources.company_boards._post_json", side_effect=[
        {"total": 21, "jobPostings": first}, {"jobPostings": []}, {"jobPostings": []},
        {"jobPostings": []}, {"jobPostings": []},
    ]), patch("applicant_zero.sources.company_boards._get_json", return_value={"jobPostingInfo": {}}) as get:
        _workday_jobs("Example", "example.wd3.myworkdayjobs.com/Careers")
    assert get.call_count == 12


def test_workday_board_is_an_accepted_public_board_type(tmp_path):
    path = tmp_path / "boards.json"
    path.write_text(json.dumps([{
        "company": "Example", "ats": "workday", "token": "example.wd3.myworkdayjobs.com/Careers"
    }]), encoding="utf-8")
    with patch("applicant_zero.sources.company_boards._workday_jobs", return_value=[]):
        _, reports = fetch_company_boards_with_report(path)
    assert reports[0].status == "checked"


def test_public_board_request_estimates_reflect_paginated_and_detail_reads():
    assert _request_count_for_board("workday", 0) == 1
    assert _request_count_for_board("workday", 21) == 5
    assert _request_count_for_board("workday", 101) == 5
    assert _request_count_for_board("smartrecruiters", 3) == 4
    assert _request_count_for_board("smartrecruiters", 101) == 14
    assert _request_count_for_board("lever", 40) == 1


def test_workday_request_estimate_includes_bounded_candidate_detail_reads():
    jobs = [
        Job("one", "Data Analyst", "Example", "Sydney", "Workday", "https://example.test/one", ""),
        Job("two", "Service Desk Analyst", "Example", "Sydney", "Workday", "https://example.test/two", ""),
        Job("three", "Unrelated role", "Example", "Sydney", "Workday", "https://example.test/three", ""),
    ]
    assert _request_count_for_board("workday", jobs) == 3


def test_request_estimate_excludes_explicitly_overseas_candidate_titles():
    jobs = [
        Job("one", "Data Analyst", "Example", "Sydney", "Workday", "https://example.test/one", ""),
        Job("two", "Data Analyst", "Example", "London, England", "Workday", "https://example.test/two", ""),
    ]
    assert _request_count_for_board("workday", jobs) == 2


def test_smartrecruiters_request_estimate_includes_only_candidate_detail_reads():
    jobs = [
        Job("one", "Data Analyst", "Example", "Sydney", "SmartRecruiters", "https://example.test/one", ""),
        Job("two", "Unrelated role", "Example", "Sydney", "SmartRecruiters", "https://example.test/two", ""),
    ]
    assert _request_count_for_board("smartrecruiters", jobs) == 2


def test_workday_search_rotation_is_stable_per_board_and_moves_daily():
    first = _workday_search_terms("Example", "example.wd3.myworkdayjobs.com/Careers", date(2026, 10, 18))
    repeat = _workday_search_terms("Example", "example.wd3.myworkdayjobs.com/Careers", date(2026, 10, 18))
    following = _workday_search_terms("Example", "example.wd3.myworkdayjobs.com/Careers", date(2026, 10, 19))
    assert first == repeat
    assert first[:2] == ("", "sydney") and len(first) == 5
    assert following[:2] == ("", "sydney") and following[2:] != first[2:]
