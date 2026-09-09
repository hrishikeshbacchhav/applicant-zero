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


def test_health_report_reads_private_discovery_log(tmp_path):
    project = tmp_path / "project"
    logs = project / "logs"
    logs.mkdir(parents=True)
    (logs / "refresh_2026-09-09_08-00-00.log").write_text(
        "Applicant Zero discovery refresh finished successfully: now", encoding="utf-8"
    )
    status = next(item for item in health_report(project) if item[0] == "Scheduled discovery log")
    assert status[1] is True
    assert "completed successfully" in status[2]
