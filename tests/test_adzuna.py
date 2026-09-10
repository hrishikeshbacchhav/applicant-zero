from unittest.mock import patch

from applicant_zero.sources.adzuna import _job_from_result, build_search_url, fetch_query_batch, fetch_query_plan


def test_search_url_targets_australia():
    url = build_search_url("id", "key", "data analyst", "Sydney")
    assert "/jobs/au/search/1" in url
    assert "what=data+analyst" in url


def test_adzuna_result_maps_to_job():
    job = _job_from_result({
        "id": "123", "title": "Power BI Analyst", "description": "Power BI and SQL",
        "redirect_url": "https://example.invalid/job", "company": {"display_name": "Example"},
        "location": {"display_name": "Sydney, NSW"},
    })
    assert job.external_id == "adzuna:123"
    assert job.company == "Example"


def test_query_batch_collapses_repeated_listings_and_keeps_going_after_one_error(tmp_path):
    first = _job_from_result({"id": "1", "title": "Data Analyst", "company": {"display_name": "Example"}, "location": {"display_name": "Sydney"}})
    second = _job_from_result({"id": "2", "title": "BI Analyst", "company": {"display_name": "Example"}, "location": {"display_name": "Sydney"}})
    with patch("applicant_zero.sources.adzuna.fetch_jobs", side_effect=[[first], RuntimeError("unavailable"), [first, second]]):
        jobs, errors = fetch_query_batch(tmp_path, ["data", "broken", "bi"])
    assert [job.external_id for job in jobs] == ["adzuna:1", "adzuna:2"]
    assert errors == ["broken: unavailable"]


def test_query_batch_accepts_zero_as_an_intentional_no_query_run(tmp_path):
    jobs, errors = fetch_query_batch(tmp_path, ["data analyst", "business analyst"], max_queries=0)
    assert jobs == []
    assert errors == []


def test_query_plan_keeps_location_specific_failures_and_deduplicates(tmp_path):
    first = _job_from_result({"id": "1", "title": "Data Analyst", "company": {"display_name": "Example"}, "location": {"display_name": "Sydney"}})
    second = _job_from_result({"id": "2", "title": "BI Analyst", "company": {"display_name": "Example"}, "location": {"display_name": "NSW"}})
    with patch("applicant_zero.sources.adzuna.fetch_jobs", side_effect=[[first], RuntimeError("unavailable"), [first, second]]):
        jobs, errors = fetch_query_plan(tmp_path, [("data", "Sydney"), ("data", "NSW"), ("bi", "Sydney")])
    assert [job.external_id for job in jobs] == ["adzuna:1", "adzuna:2"]
    assert errors == ["data (NSW): unavailable"]
