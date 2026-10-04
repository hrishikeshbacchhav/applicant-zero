from unittest.mock import patch

from applicant_zero.sources.himalayas import _job_from_result, build_jobs_url, build_search_url, fetch_jobs_with_report, fetch_targeted_jobs_with_report


def test_himalayas_request_caps_page_size_and_preserves_returned_cursor():
    assert build_jobs_url(limit=999).endswith("limit=20")
    assert "cursor=opaque-token" in build_jobs_url(cursor="opaque-token")
    search_url = build_search_url(query="data analyst", country="AU")
    assert search_url.startswith("https://himalayas.app/jobs/api/search?")
    assert "q=data+analyst" in search_url
    assert "country=AU" in search_url


def test_himalayas_mapping_preserves_attribution_and_application_detail():
    job = _job_from_result({
        "guid": "42", "title": "Data Analyst", "companyName": "Example", "locationRestrictions": ["Australia"],
        "applicationLink": "https://example.test/apply", "description": "<p>SQL reporting</p>",
        "employmentType": "Full Time", "pubDate": "2026-09-25", "minSalary": 90000, "maxSalary": 100000,
        "currency": "AUD", "salaryPeriod": "annual",
    })
    assert job.external_id == "himalayas:42"
    assert job.location == "Remote, Australia"
    assert job.url == "https://example.test/apply"
    assert "Application link: https://example.test/apply" in job.description
    assert "Compensation: 90000–100000 AUD per annual" in job.description


def test_himalayas_fetch_follows_a_returned_cursor_with_hard_page_cap():
    class Response:
        def __init__(self, payload): self.payload = payload
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self): return self.payload
    responses = [
        Response(b'{"jobs":[{"guid":"one","title":"Data Analyst"}],"nextCursor":"next"}'),
        Response(b'{"jobs":[{"guid":"two","title":"IT Support Officer"}]}'),
    ]
    with patch("applicant_zero.sources.himalayas.urlopen", side_effect=responses):
        jobs, report = fetch_jobs_with_report(max_pages=5)
    assert [job.external_id for job in jobs] == ["himalayas:one", "himalayas:two"]
    assert report.requests == 2


def test_himalayas_targeted_search_uses_distinct_campaign_terms_and_keeps_partial_results():
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self): return b'{"jobs":[{"guid":"one","title":"Data Analyst"}]}'

    with patch(
        "applicant_zero.sources.himalayas.urlopen",
        side_effect=[Response(), OSError("temporary source issue")],
    ):
        jobs, report = fetch_targeted_jobs_with_report(
            ["data analyst", "Data Analyst", "IT support"], max_queries=5
        )
    assert [job.external_id for job in jobs] == ["himalayas:one"]
    assert report.requests == 2
    assert report.errors == ("IT support: temporary source issue",)


def test_himalayas_targeted_search_falls_back_to_bounded_browse_without_campaign_terms():
    with patch("applicant_zero.sources.himalayas.fetch_jobs_with_report", return_value=([], object())) as fallback:
        jobs, report = fetch_targeted_jobs_with_report([], max_queries=3)
    assert jobs == []
    assert report is fallback.return_value[1]
    fallback.assert_called_once_with(max_pages=3)
