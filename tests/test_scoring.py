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
    assert "unrestricted work-rights requirement" in result.missing_requirements


def test_data_engineering_role_is_not_mistaken_for_a_data_analyst_role():
    job = Job("8", "Data Engineer", "Example", "Sydney, NSW", "test", "https://example.invalid", "Build pipelines in Python and SQL.")
    assert score_job(job, RISHI_PROFILE).recommendation == "Skip"


def test_clearance_condition_stays_visible_for_candidate_review():
    job = Job("9", "Data Analyst", "Example", "Sydney, NSW", "test", "https://example.invalid", "Australian citizenship and baseline clearance are required.")
    result = score_job(job, RISHI_PROFILE)
    assert result.recommendation == "Review"
    assert "Australian citizenship required" in result.missing_requirements


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
    assert result.resume_family == "it_support"
    assert "IT-support route" in " ".join(result.reasons)


def test_nsw_only_location_is_held_for_location_review_not_discarded():
    job = Job("nsw", "Data Analyst", "Example", "NSW", "test", "https://example.invalid", "SQL and Power BI")
    result = score_job(job, RISHI_PROFILE)
    assert result.recommendation in {"Apply", "Strong apply", "Review"}
    assert "labelled NSW" in " ".join(result.reasons)


def test_inactive_campaign_lane_does_not_clutter_the_active_queue():
    job = Job("admin", "Administration Officer", "Example", "Sydney", "test", "https://example.invalid", "Administration and customer service")
    result = score_job(job, RISHI_PROFILE, {"data_bi"})
    assert result.recommendation == "Skip"
    assert result.lane == "administration"


def test_full_time_administration_campaign_filters_explicit_part_time_work():
    job = Job(
        "admin-part-time", "Administration Officer", "Example", "Sydney", "test", "https://example.invalid",
        "Part-time administration role supporting the customer service team.",
    )
    result = score_job(job, RISHI_PROFILE, {"administration"})
    assert result.recommendation == "Skip"
    assert "full-time administration campaign" in " ".join(result.reasons)


def test_full_time_administration_campaign_keeps_explicit_full_time_work():
    job = Job(
        "admin-full-time", "Administration Officer", "Example", "Sydney", "test", "https://example.invalid",
        "Full-time administration role supporting the customer service team.",
    )
    result = score_job(job, RISHI_PROFILE, {"administration"})
    assert result.recommendation in {"Apply", "Review", "Strong apply"}


def test_data_governance_role_is_discovered_as_data_analytics():
    job = Job("13", "Data Governance Analyst", "Example", "Sydney, NSW", "test", "https://example.invalid", "Data quality, SQL and stakeholder engagement.")
    assert score_job(job, RISHI_PROFILE).recommendation in {"Apply", "Strong apply", "Review"}


def test_role_lane_is_saved_with_the_result_for_queue_filtering():
    job = Job("14", "IT Service Desk Analyst", "Example", "Sydney", "test", "https://example.invalid", "Technical support and stakeholder communication.")
    assert score_job(job, RISHI_PROFILE).lane == "it_support"


def test_bi_developer_is_kept_in_the_power_bi_route():
    job = Job("15", "Business Intelligence Developer", "Example", "Sydney", "test", "https://example.invalid", "Power BI, DAX, SQL and Microsoft Fabric.")
    result = score_job(job, RISHI_PROFILE)
    assert result.resume_family == "power_bi"
    assert result.recommendation in {"Apply", "Strong apply"}


def test_unrelated_analyst_title_is_filtered_before_it_clutters_queue():
    job = Job("16", "Talent Analytics Analyst", "Example", "Sydney", "test", "https://example.invalid", "Power BI and SQL.")
    result = score_job(job, RISHI_PROFILE)
    assert result.recommendation == "Skip"
    assert "outside the selected" in " ".join(result.reasons)


def test_unverified_sector_and_leadership_requirements_hold_role_for_review():
    job = Job(
        "17",
        "Business and Process Analyst",
        "Example",
        "Sydney, NSW",
        "test",
        "https://example.invalid",
        "Lead the requirements gathering and delivery planning for initiatives from our Continuous Improvement Plan. Aged care sector experience is required.",
    )
    result = score_job(job, RISHI_PROFILE)
    assert result.recommendation == "Review"
    assert "independent requirements-gathering leadership" in result.missing_requirements
    assert "direct care-sector experience" in result.missing_requirements
    assert "continuous-improvement delivery experience" in result.missing_requirements



def test_broader_supported_title_vocabulary_keeps_discoverable_roles_visible():
    examples = [
        ("Data Visualisation Analyst", "data_bi"),
        ("Business Improvement Analyst", "business_analysis"),
        ("ICT Support Officer", "it_support"),
        ("Graduate Technology Analyst", "it_general"),
        ("Administration Assistant", "administration"),
    ]
    enabled = {"data_bi", "business_analysis", "it_support", "it_general", "administration"}
    for index, (title, lane) in enumerate(examples):
        result = score_job(Job(f"expanded-{index}", title, "Example", "Sydney, NSW", "test", "https://example.invalid", "SQL, Excel, technical support and stakeholder communication."), RISHI_PROFILE, enabled)
        assert result.recommendation != "Skip"
        assert result.lane == lane


def test_unrelated_analyst_work_is_still_kept_out_of_broader_vocabulary():
    result = score_job(Job("noise", "SEO Analyst", "Example", "Sydney", "test", "https://example.invalid", "Analytics and reporting."), RISHI_PROFILE)
    assert result.recommendation == "Skip"
