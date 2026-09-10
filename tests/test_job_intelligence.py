from applicant_zero.job_intelligence import inspect_job


def test_listing_intelligence_extracts_public_job_details_without_guessing():
    result = inspect_job(
        "Data Analyst",
        "NSW",
        "Full-time role. Salary $90,000 - $110,000 plus super. "
        "Applications close: 30 September 2026. Contact careers@example.com.",
    )

    assert result.salary == "AUD 90,000–110,000 base salary, where stated in the listing"
    assert result.contacts == ("careers@example.com",)
    assert result.closing_detail == "30 September 2026"
    assert result.employment_type == "Full-time"
    assert result.location_signal == "NSW only — confirm the workplace"


def test_listing_intelligence_marks_absent_information_as_not_stated():
    result = inspect_job("Analyst", "Australia", "Build reports using SQL.")

    assert result.salary == ""
    assert result.contacts == ()
    assert result.closing_detail == ""
    assert result.employment_type == "Not stated"
    assert result.location_signal == "Check the listed workplace"
