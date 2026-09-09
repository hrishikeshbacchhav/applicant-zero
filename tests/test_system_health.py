import json

from applicant_zero.storage import initialise_database

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


def test_health_report_detects_a_real_snapshot(tmp_path):
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
    with initialise_database(project / "data" / "applicant_zero.sqlite3"):
        pass
    backup_dir = project / "data" / "backups"
    backup_dir.mkdir()
    (backup_dir / "applicant_zero-dashboard.sqlite3").write_bytes(b"snapshot")

    backups = next(item for item in health_report(project) if item[0] == "Private backups")

    assert backups[1] is True
    assert "Latest snapshot" in backups[2]
