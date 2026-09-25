from unittest.mock import patch

from applicant_zero.sources.remotive import _job_from_result, build_jobs_url, fetch_jobs


def test_remotive_request_is_bounded():
    assert build_jobs_url(count=999).endswith("limit=200")


def test_remotive_mapping_preserves_listing_attribution_and_metadata():
    job = _job_from_result({
        "id": 42, "title": "Data Analyst", "company_name": "Example", "candidate_required_location": "Australia",
        "url": "https://remotive.com/remote-jobs/data/example-42", "description": "<p>SQL reporting</p>",
        "job_type": "full_time", "publication_date": "2026-09-24", "salary": "$90,000 - $100,000",
    })
    assert job.external_id == "remotive:42"
    assert job.location == "Remote, Australia"
    assert job.url == "https://remotive.com/remote-jobs/data/example-42"
    assert "Published: 2026-09-24" in job.description
    assert "Compensation: $90,000 - $100,000" in job.description


def test_remotive_fetch_maps_public_response():
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self): return b'{"jobs":[{"id":1,"title":"IT Support Officer"}]}'
    with patch("applicant_zero.sources.remotive.urlopen", return_value=Response()):
        jobs = fetch_jobs(count=1)
    assert [(job.external_id, job.source) for job in jobs] == [("remotive:1", "Remotive")]
