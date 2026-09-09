from applicant_zero.candidate_facts import build_fact_library, ensure_fact_library
from applicant_zero.contracts import FactClass


def test_fact_library_classifies_reusable_and_protected_values(tmp_path):
    profile = {
        "contact": {"legal_name": "Rishi Example", "email": "r@example.com", "phone": "1", "current_location": "Sydney"},
        "availability": {"full_time_from": "2026-11-15"},
        "identity": {"pronouns": "he/him"},
        "eligibility": {"visa_type": "Subclass 500", "current_work_rights": "Confirmed status"},
    }
    facts = {fact.key: fact for fact in build_fact_library(profile, {"answers_requiring_confirmation": {"notice_period": "4 weeks"}})}
    assert facts["pronouns"].usable_for_ordinary_field
    assert facts["visa_type"].fact_class is FactClass.PROTECTED
    payload = ensure_fact_library(tmp_path, profile)
    assert payload["schema_version"] == 1
    assert (tmp_path / "private" / "candidate_facts.json").exists()
