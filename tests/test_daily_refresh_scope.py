from applicant_zero.__main__ import _inventory_scope_jobs
from applicant_zero.scoring import Job


def job(identifier: str, title: str, location: str = "Sydney") -> Job:
    return Job(identifier, title, "Example", location, "Public board", "https://example.test", "")


def test_inventory_keeps_candidate_role_lanes_even_if_the_campaign_is_currently_disabled():
    scoped = _inventory_scope_jobs([
        job("data", "Data Analyst"),
        job("support", "IT Support Officer"),
        job("admin", "Administration Officer"),
        job("unrelated", "Registered Nurse"),
        job("interstate", "Data Analyst", "Melbourne"),
    ])
    assert [item.external_id for item in scoped] == ["data", "support", "admin"]


def test_inventory_keeps_a_senior_candidate_lane_role_for_review():
    scoped = _inventory_scope_jobs([job("senior", "Senior Data Analyst")])
    assert [item.external_id for item in scoped] == ["senior"]
