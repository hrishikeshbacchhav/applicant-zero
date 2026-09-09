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


def test_adjacent_analytics_role_requires_review_before_applying():
    job = Job("5", "Commercial Pricing Analyst", "Example", "Sydney, NSW", "test", "https://example.invalid", "SQL, Excel and stakeholder reporting.")
    result = score_job(job, RISHI_PROFILE)
    assert result.recommendation == "Review"
    assert result.resume_family == "data_bi"


def test_high_experience_requirement_is_flagged_even_without_senior_title():
    job = Job("6", "Data Analyst", "Example", "Sydney, NSW", "test", "https://example.invalid", "Applicants require at least 5 years of relevant experience with SQL.")
    result = score_job(job, RISHI_PROFILE)
    assert result.recommendation == "Review"
    assert result.score == 35
    assert "5+ years of experience" in result.missing_requirements


def test_work_rights_condition_is_shown_as_a_requirement_to_check():
    job = Job("7", "Data Analyst", "Example", "Sydney, NSW", "test", "https://example.invalid", "Power BI and SQL. Applicants must have unrestricted working rights in Australia.")
    result = score_job(job, RISHI_PROFILE)
    assert "work-rights eligibility" in result.missing_requirements


def test_data_engineering_role_is_not_mistaken_for_a_data_analyst_role():
    job = Job("8", "Data Engineer", "Example", "Sydney, NSW", "test", "https://example.invalid", "Build pipelines in Python and SQL.")
    assert score_job(job, RISHI_PROFILE).recommendation == "Skip"


def test_clearance_condition_stays_visible_for_candidate_review():
    job = Job("9", "Data Analyst", "Example", "Sydney, NSW", "test", "https://example.invalid", "Australian citizenship and baseline clearance are required.")
    result = score_job(job, RISHI_PROFILE)
    assert result.recommendation == "Review"
    assert "eligibility or clearance requirement" in result.missing_requirements


def test_unmatched_direct_role_is_kept_for_review_not_auto_apply():
    job = Job("10", "Data Analyst", "Example", "Sydney, NSW", "test", "https://example.invalid", "Lead pricing governance and commercial policy work.")
    result = score_job(job, RISHI_PROFILE)
    assert result.recommendation == "Review"
    assert "No direct skills from your verified evidence" in " ".join(result.reasons)


def test_named_gap_prevents_a_strong_apply_label():
    job = Job("11", "Graduate Power BI Analyst", "Example", "Sydney, NSW", "test", "https://example.invalid", "Power BI, DAX, SQL, Power Query, Microsoft Fabric and Azure are essential.")
    result = score_job(job, RISHI_PROFILE)
    assert result.score >= 78
    assert result.recommendation == "Apply"
    assert "azure" in result.missing_requirements


def test_service_desk_role_is_routed_to_review_not_discarded():
    job = Job("12", "IT Service Desk Analyst", "Example", "Sydney, NSW", "test", "https://example.invalid", "Provide technical support, resolve incidents and communicate with stakeholders.")
    result = score_job(job, RISHI_PROFILE)
    assert result.recommendation == "Review"
    assert result.resume_family == "data_bi"
    assert "IT-support route" in " ".join(result.reasons)


def test_data_governance_role_is_discovered_as_data_analytics():
    job = Job("13", "Data Governance Analyst", "Example", "Sydney, NSW", "test", "https://example.invalid", "Data quality, SQL and stakeholder engagement.")
    assert score_job(job, RISHI_PROFILE).recommendation in {"Apply", "Strong apply", "Review"}


def test_role_lane_is_saved_with_the_result_for_queue_filtering():
    job = Job("14", "IT Service Desk Analyst", "Example", "Sydney", "test", "https://example.invalid", "Technical support and stakeholder communication.")
    assert score_job(job, RISHI_PROFILE).lane == "it_support"
