from unittest.mock import patch

from applicant_zero.sources.jobicy import _job_from_result, build_jobs_url, fetch_jobs


def test_jobicy_request_is_bounded_to_public_apac_feed():
    url = build_jobs_url(count=999, geo="APAC")
    assert "count=200" in url
    assert "geo=apac" in url


def test_jobicy_mapping_preserves_attribution_and_listing_metadata():
    job = _job_from_result({
        "id": 42, "jobTitle": "Data Analyst", "companyName": "Example", "jobGeo": "Australia",
        "url": "https://jobicy.com/jobs/example-42", "jobDescription": "<p>SQL reporting</p>",
        "jobType": ["Full-Time"], "jobIndustry": ["Data Science"], "pubDate": "2026-09-24",
    })
    assert job.external_id == "jobicy:42"
    assert job.location == "Remote, Australia"
    assert job.url == "https://jobicy.com/jobs/example-42"
    assert "Published: 2026-09-24" in job.description
    assert "Employment type: Full-Time" in job.description


def test_jobicy_fetch_maps_public_response():
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self): return b'{"jobs":[{"id":1,"jobTitle":"IT Support Officer"}]}'
    with patch("applicant_zero.sources.jobicy.urlopen", return_value=Response()):
        jobs = fetch_jobs(count=1)
    assert [(job.external_id, job.source) for job in jobs] == [("jobicy:1", "Jobicy")]
