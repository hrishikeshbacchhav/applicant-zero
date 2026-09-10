import json

from applicant_zero.material_manifest import create_material_manifest, material_manifest_path
from applicant_zero.profile import RISHI_PROFILE
from applicant_zero.scoring import Job, score_job
from applicant_zero.storage import initialise_database, save_match


def test_manifest_records_the_resume_route_and_evidence(tmp_path):
    private = tmp_path / "private"
    private.mkdir()
    resume = private / "data.pdf"
    resume.write_text("resume", encoding="utf-8")
    master = private / "data.docx"
    master.write_text("master", encoding="utf-8")
    (private / "candidate_profile.json").write_text(json.dumps({
        "contact": {"legal_name": "Rishi", "email": "r@example.com", "phone": "0400", "current_location": "Sydney"},
        "availability": {"full_time_from": "2026-11-15"},
        "eligibility": {"current_work_rights": "Verified", "requires_sponsorship_answer": "No"},
        "resumes": {"data_bi": str(resume), "power_bi": str(resume), "business_analysis": str(resume)},
        "editable_resume_masters": {"data_bi": str(master)},
    }), encoding="utf-8")
    database_path = tmp_path / "data" / "jobs.sqlite3"
    with initialise_database(database_path) as database:
        job = Job("job-1", "Data Analyst", "Example", "Sydney", "test", "https://example.invalid", "Full-time. Salary $90,000 - $110,000. Contact careers@example.com. SQL and Power BI")
        save_match(database, job, score_job(job, RISHI_PROFILE))

    path = create_material_manifest(database_path, "job-1")

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["job"]["listing_fingerprint"]
    assert payload["resume_route"]["approved_pdf"] == str(resume)
    assert "sql" in payload["evidence"]["matched"]
    assert payload["listing_intelligence"]["salary"].startswith("AUD 90,000")
    assert payload["listing_intelligence"]["contacts"] == ["careers@example.com"]
    assert material_manifest_path(database_path, "job-1") == path
