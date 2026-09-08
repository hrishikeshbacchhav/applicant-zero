from unittest.mock import patch

from applicant_zero.sources.company_boards import _greenhouse_jobs, _lever_jobs


def test_greenhouse_mapping():
    payload = {"jobs": [{"id": 7, "title": "Data Analyst", "location": {"name": "Sydney, NSW"}, "absolute_url": "https://example.invalid", "content": "SQL and Power BI"}]}
    with patch("applicant_zero.sources.company_boards._get_json", return_value=payload):
        jobs = _greenhouse_jobs("Example", "token")
    assert jobs[0].external_id == "greenhouse:token:7"
    assert jobs[0].location == "Sydney, NSW"


def test_lever_mapping():
    payload = [{"id": "9", "text": "Business Analyst", "categories": {"location": "Sydney, NSW"}, "hostedUrl": "https://example.invalid", "descriptionPlain": "Requirements gathering"}]
    with patch("applicant_zero.sources.company_boards._get_json", return_value=payload):
        jobs = _lever_jobs("Example", "token")
    assert jobs[0].external_id == "lever:token:9"
    assert jobs[0].title == "Business Analyst"
