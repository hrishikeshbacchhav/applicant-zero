from applicant_zero.profile import RISHI_PROFILE
from applicant_zero.scoring import Job, score_job


def test_power_bi_job_is_strongly_matched():
    job = Job("1", "Graduate Power BI Analyst", "Example", "Sydney, NSW", "test", "https://example.invalid", "Power BI, DAX, SQL, Power Query and Microsoft Fabric.")
    result = score_job(job, RISHI_PROFILE)
    assert result.recommendation == "Strong apply"
    assert result.resume_family == "power_bi"


def test_outside_location_is_skipped():
    job = Job("2", "Data Analyst", "Example", "Melbourne, VIC", "test", "https://example.invalid", "SQL and Power BI.")
    result = score_job(job, RISHI_PROFILE)
    assert result.recommendation == "Skip"


def test_senior_role_is_reviewed():
    job = Job("3", "Senior Data Analyst", "Example", "Sydney, NSW", "test", "https://example.invalid", "Requires 5+ years of experience.")
    result = score_job(job, RISHI_PROFILE)
    assert result.recommendation == "Review"


def test_description_mentioning_manager_does_not_make_a_junior_role_senior():
    job = Job("4", "Junior Business Analyst", "Example", "Sydney, NSW", "test", "https://example.invalid", "Work with a manager on requirements gathering and process mapping.")
    result = score_job(job, RISHI_PROFILE)
    assert result.recommendation != "Review"
