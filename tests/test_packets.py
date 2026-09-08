import json

from applicant_zero.packets import create_application_packet
from applicant_zero.profile import RISHI_PROFILE
from applicant_zero.scoring import Job, score_job
from applicant_zero.storage import initialise_database, save_match


def test_packet_is_written_inside_private_directory(tmp_path):
    project = tmp_path / "project"
    database_path = project / "data" / "jobs.sqlite3"
    private = project / "private"
    private.mkdir(parents=True)
    resumes = {}
    for family in ("data_bi", "power_bi", "business_analysis"):
        resume = private / f"{family}.pdf"
        resume.write_text("resume", encoding="utf-8")
        resumes[family] = str(resume)
    (private / "candidate_profile.json").write_text(json.dumps({
        "contact": {"legal_name": "Rishi", "email": "a@b.com", "phone": "1", "current_location": "Sydney"},
        "availability": {"full_time_from": "2026-11-15"},
        "eligibility": {"current_work_rights": "status", "requires_sponsorship_answer": "No"},
        "resumes": resumes,
    }), encoding="utf-8")
    database = initialise_database(database_path)
    job = Job("job-1", "Data Analyst", "Example Co", "Sydney", "test", "https://example.invalid", "Power BI and SQL")
    save_match(database, job, score_job(job, RISHI_PROFILE))
    packet = create_application_packet(database_path, "job-1")
    assert packet.parent == private / "application_packets"
    assert "Example Co" in packet.read_text(encoding="utf-8")
