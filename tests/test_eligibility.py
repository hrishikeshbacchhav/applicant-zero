from applicant_zero.eligibility import evaluate_listing_eligibility, listing_eligibility_requirements


def test_explicit_citizenship_requirement_blocks_a_student_visa_profile():
    profile = {"eligibility": {"visa_type": "Subclass 500", "citizenship_status": "Not an Australian citizen"}}
    result = evaluate_listing_eligibility("Applicants must be an Australian citizen and hold baseline clearance.", profile)
    assert result.outcome == "blocked"
    assert "Australian citizenship required" in result.requirements


def test_clearance_requirement_requires_confirmation_not_a_guess():
    result = evaluate_listing_eligibility("A baseline clearance is required.", {"eligibility": {}})
    assert result.outcome == "confirm"
    assert "security clearance requirement" in result.requirements


def test_no_eligibility_phrase_is_clear():
    assert evaluate_listing_eligibility("Build Power BI reporting with stakeholders.", {}).outcome == "clear"


def test_requirement_detection_covers_sponsorship_and_work_rights():
    requirements = listing_eligibility_requirements("You need full working rights and no visa sponsorship.")
    assert {kind for _, kind in requirements} == {"work_rights", "sponsorship"}
