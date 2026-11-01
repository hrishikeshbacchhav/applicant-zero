from unittest.mock import patch
from datetime import date
from urllib.parse import parse_qs, urlparse

from applicant_zero.sources.remoteok import API_URL, _daily_target_tags, _job_from_result, build_jobs_url, fetch_jobs, fetch_targeted_jobs


def test_remoteok_mapping_skips_legal_record_and_preserves_canonical_attribution():
    assert _job_from_result({"legal": "Remote OK attribution text"}) is None
    job = _job_from_result({
        "id": "42", "position": "Data Analyst", "company": "Example", "location": "Worldwide",
        "slug": "remote-data-analyst-42", "description": "<p>SQL reporting</p>",
        "tags": ["data", "sql"], "date": "2026-10-05", "salary_min": 90000, "salary_max": 100000,
    })
    assert job is not None
    assert job.external_id == "remoteok:42"
    assert job.location == "Remote, Worldwide"
    assert job.url == "https://remoteok.com/remote-jobs/remote-data-analyst-42"
    assert "Tags: data, sql" in job.description
    assert "Compensation: 90000–100000 USD" in job.description


def test_remoteok_fetch_uses_one_public_feed_and_hard_item_cap():
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self): return b'[{"legal":"notice"},{"id":"1","position":"IT Support"},{"id":"2","position":"Data Analyst"}]'

    with patch("applicant_zero.sources.remoteok.urlopen", return_value=Response()) as request:
        jobs = fetch_jobs(max_items=1)
    assert [job.external_id for job in jobs] == ["remoteok:1"]
    assert request.call_args.args[0].full_url == API_URL


def test_remoteok_uses_documented_exact_tag_filter_and_rotates_bounded_tags():
    assert parse_qs(urlparse(build_jobs_url(tag="data")).query) == {"tag": ["data"]}
    assert _daily_target_tags(date(2026, 10, 31)) != _daily_target_tags(date(2026, 11, 1))
    assert len(_daily_target_tags(date(2026, 10, 31))) == 4


def test_remoteok_targeted_fetch_keeps_successful_tags_when_one_fails():
    def reader(*, tag="", **_):
        if tag == "support":
            raise OSError("temporary failure")
        return [_job_from_result({"id": tag, "position": f"{tag} analyst", "company": "Example"})]

    with patch("applicant_zero.sources.remoteok.fetch_jobs", side_effect=reader):
        jobs, report = fetch_targeted_jobs(tags=("data", "support", "admin"))

    assert [job.external_id for job in jobs] == ["remoteok:data", "remoteok:admin"]
    assert report.requests == 3
    assert report.errors == ("support: temporary failure",)
