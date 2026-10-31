from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from applicant_zero.sources.themuse import _job_from_result, build_jobs_url, configured, fetch_targeted_jobs


def test_themuse_request_is_registered_and_bounded_to_one_category_page():
    url = build_jobs_url("private-key", category="Data and Analytics", location="Australia", page=0)
    params = parse_qs(urlparse(url).query)

    assert params["api_key"] == ["private-key"]
    assert params["category"] == ["Data and Analytics"]
    assert params["location"] == ["Australia"]
    assert params["page"] == ["0"]


def test_themuse_mapping_preserves_provider_landing_page_and_metadata():
    job = _job_from_result({
        "id": 42,
        "name": "Data Analyst",
        "company": {"name": "Example"},
        "locations": [{"name": "Sydney, Australia"}],
        "levels": [{"name": "Entry Level"}],
        "categories": [{"name": "Data and Analytics"}],
        "contents": "<p>SQL reporting</p>",
        "refs": {"landing_page": "https://www.themuse.com/jobs/example/data-analyst"},
        "publication_date": "2026-10-31T10:00:00Z",
        "type": "External",
    })

    assert job.external_id == "themuse:42"
    assert job.location == "Sydney, Australia"
    assert job.url == "https://www.themuse.com/jobs/example/data-analyst"
    assert job.seniority == "Entry Level"
    assert "Published: 2026-10-31T10:00:00Z" in job.description


def test_themuse_reads_only_the_bounded_selected_categories(tmp_path, monkeypatch):
    monkeypatch.setenv("THEMUSE_API_KEY", "local-test-key")

    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self): return b'{"results":[{"id":1,"name":"IT Support Officer","company":{"name":"Example"}}]}'

    with patch("applicant_zero.sources.themuse.urlopen", return_value=Response()) as reader:
        jobs, report = fetch_targeted_jobs(tmp_path, categories=("Computer and IT", "Data and Analytics", "Business Operations"), max_requests=2)

    assert [job.external_id for job in jobs] == ["themuse:1", "themuse:1"]
    assert report.requests == 2
    assert not report.errors
    assert reader.call_count == 2


def test_themuse_is_disabled_without_a_local_registered_key(tmp_path, monkeypatch):
    monkeypatch.delenv("THEMUSE_API_KEY", raising=False)
    assert not configured(tmp_path)
