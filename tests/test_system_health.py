import json

from applicant_zero.system_health import health_report


def test_health_report_identifies_ready_private_profile(tmp_path):
    project = tmp_path / "project"
    private = project / "private"
    private.mkdir(parents=True)
    resumes = {}
    for family in ("data_bi", "power_bi", "business_analysis"):
        file = private / f"{family}.pdf"
        file.write_text("resume", encoding="utf-8")
        resumes[family] = str(file)
    (private / "candidate_profile.json").write_text(json.dumps({
        "contact": {"legal_name": "Rishi", "email": "r@example.com", "phone": "0400", "current_location": "Sydney"},
        "availability": {"full_time_from": "2026-11-15"},
        "eligibility": {"current_work_rights": "Verified", "requires_sponsorship_answer": "No"},
        "resumes": resumes,
    }), encoding="utf-8")
    report = health_report(project)
    assert report[0][1] is True
    assert report[1][1] is True
