import json

from applicant_zero import resume_evidence


def _profile(private, pdf):
    (private / "candidate_profile.json").write_text(json.dumps({
        "contact": {"legal_name": "Rishi", "email": "r@example.com", "phone": "0400", "current_location": "Sydney"},
        "availability": {"full_time_from": "2026-11-15"},
        "eligibility": {"current_work_rights": "Verified", "requires_sponsorship_answer": "No"},
        "resumes": {"data_bi": str(pdf), "power_bi": str(pdf), "business_analysis": str(pdf)},
    }), encoding="utf-8")


def test_candidate_lines_are_original_deduplicated_source_text():
    lines = resume_evidence._candidate_lines("Short\nBuilt Power BI reporting for internal stakeholders and improved data quality.\nBuilt Power BI reporting for internal stakeholders and improved data quality.\n")
    assert lines == ["Built Power BI reporting for internal stakeholders and improved data quality."]


def test_inventory_is_private_and_read_only(monkeypatch, tmp_path):
    private = tmp_path / "private"
    private.mkdir()
    pdf = private / "resume.pdf"
    pdf.write_bytes(b"unchanged")
    _profile(private, pdf)
    monkeypatch.setattr(resume_evidence, "_extract", lambda _: (1, "Built Power BI reporting for internal stakeholders and improved data quality."))

    path = resume_evidence.create_resume_evidence_inventory(tmp_path)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["resumes"]["data_bi"]["filename"] == "resume.pdf"
    assert resume_evidence.load_lane_resume_evidence(tmp_path, "data_bi")
    assert pdf.read_bytes() == b"unchanged"
