from applicant_zero.sources.adzuna import _job_from_result, build_search_url


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
