from unittest.mock import patch

from applicant_zero.sources.jobdatalake import _job_from_result, build_search_url, run_trial


def test_jobdatalake_url_is_australia_and_full_time_scoped():
    url = build_search_url("secret", "data analyst")
    assert "countries=AU" in url
    assert "employment_type=full_time" in url
    assert "secret" not in url


def test_jobdatalake_result_maps_to_standard_job():
    job = _job_from_result({"job_handle": "role", "title": "Data Analyst", "company_name": "Example", "locations": ["Sydney, NSW"], "url": "https://example.test", "required_skills": ["SQL"]})
    assert job.external_id == "jobdatalake:role"
    assert job.source == "JobDataLake"
    assert "SQL" in job.description


def test_jobdatalake_mapping_retains_provider_freshness_and_employment_metadata():
    job = _job_from_result({
        "job_handle": "metadata", "title": "Data Analyst", "company_name": "Example", "locations": ["Sydney"],
        "posted_at": "2026-09-18", "employment_type": "full_time", "salary_min": 90000, "salary_max": 110000,
    })
    assert "Published: 2026-09-18" in job.description
    assert "Employment type: full_time" in job.description
    assert "Compensation: AUD 90,000 - 110,000" in job.description


def test_trial_is_bounded_and_keeps_going_after_an_issue(tmp_path, monkeypatch):
    monkeypatch.setenv("JOBDATALAKE_API_KEY", "test-key")
    job = _job_from_result({"job_handle": "one", "title": "Data Analyst", "company_name": "Example", "locations": ["Sydney"], "url": "https://example.test"})
    with patch("applicant_zero.sources.jobdatalake.fetch_jobs", side_effect=[[job], RuntimeError("unavailable"), [job]]):
        jobs, reports = run_trial(tmp_path, ["data", "broken", "bi"], max_requests=2)
    assert [item.external_id for item in jobs] == ["jobdatalake:one"]
    assert len(reports) == 2
    assert reports[1].error == "unavailable"


def test_trial_with_no_local_key_is_reported_without_consuming_a_request(tmp_path, monkeypatch):
    monkeypatch.delenv("JOBDATALAKE_API_KEY", raising=False)
    jobs, reports = run_trial(tmp_path, ["data analyst"], max_requests=5)
    assert jobs == []
    assert reports[0].requests == 0
    assert "Missing JOBDATALAKE_API_KEY" in reports[0].error
