import json

from applicant_zero.profile import RISHI_PROFILE
from applicant_zero.resume_output import create_editable_resume_copy, editable_resume_copy_exists
from applicant_zero.scoring import Job, score_job
from applicant_zero.storage import initialise_database, save_match


def test_creates_job_specific_word_copy_without_changing_master(tmp_path):
    project = tmp_path / "project"
    private = project / "private"
    private.mkdir(parents=True)
    master = private / "data-bi.docx"
    master.write_text("editable master", encoding="utf-8")
    resumes = {}
    for family in ("data_bi", "power_bi", "business_analysis"):
        pdf = private / f"{family}.pdf"
        pdf.write_text("pdf", encoding="utf-8")
        resumes[family] = str(pdf)
    (private / "candidate_profile.json").write_text(json.dumps({
        "contact": {"legal_name": "Rishi", "email": "r@example.com", "phone": "0400", "current_location": "Sydney"},
        "availability": {"full_time_from": "2026-11-15"},
        "eligibility": {"current_work_rights": "Verified", "requires_sponsorship_answer": "No"},
        "resumes": resumes,
        "editable_resume_masters": {"data_bi": str(master)},
    }), encoding="utf-8")
    database_path = project / "data" / "jobs.sqlite3"
    database = initialise_database(database_path)
    job = Job("job-1", "Data Analyst", "Example", "Sydney", "test", "https://example.invalid", "SQL")
    save_match(database, job, score_job(job, RISHI_PROFILE))
    output = create_editable_resume_copy(database_path, job.external_id)
    assert output.read_text(encoding="utf-8") == "editable master"
    assert master.read_text(encoding="utf-8") == "editable master"
    assert editable_resume_copy_exists(database_path, job.external_id)
