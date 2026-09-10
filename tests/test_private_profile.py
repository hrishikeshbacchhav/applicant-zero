import json

from applicant_zero.private_profile import check_profile, load_profile


def test_profile_check_identifies_missing_file():
    assert check_profile(__import__("pathlib").Path("missing-profile.json")) == ["Candidate profile file is missing."]


def test_profile_check_accepts_complete_profile(tmp_path):
    resumes = {}
    for family in ("data_bi", "power_bi", "business_analysis"):
        path = tmp_path / f"{family}.pdf"
        path.write_text("placeholder", encoding="utf-8")
        resumes[family] = str(path)
    profile = {
        "contact": {"legal_name": "Rishi", "email": "r@example.com", "phone": "000", "current_location": "Sydney"},
        "availability": {"full_time_from": "2026-11-15"},
        "eligibility": {"current_work_rights": "Current status", "requires_sponsorship_answer": "Answer"},
        "resumes": resumes,
    }
    path = tmp_path / "candidate_profile.json"
    path.write_text(json.dumps(profile), encoding="utf-8")
    assert check_profile(path) == []
    assert load_profile(path)["contact"]["legal_name"] == "Rishi"


def test_profile_check_validates_optional_editable_word_masters(tmp_path):
    resumes = {}
    for family in ("data_bi", "power_bi", "business_analysis"):
        path = tmp_path / f"{family}.pdf"
        path.write_text("placeholder", encoding="utf-8")
        resumes[family] = str(path)
    profile = {
        "contact": {"legal_name": "Rishi", "email": "r@example.com", "phone": "000", "current_location": "Sydney"},
        "availability": {"full_time_from": "2026-11-15"},
        "eligibility": {"current_work_rights": "Current status", "requires_sponsorship_answer": "Answer"},
        "resumes": resumes,
        "editable_resume_masters": {"data_bi": str(tmp_path / "missing.pdf")},
    }
    path = tmp_path / "candidate_profile.json"
    path.write_text(json.dumps(profile), encoding="utf-8")
    assert "Check the editable Word master for data_bi." in check_profile(path)
