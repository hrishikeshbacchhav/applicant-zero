import json

from applicant_zero.operations import operational_queue, prepare_eligible_roles
from applicant_zero.profile import RISHI_PROFILE
from applicant_zero.scoring import Job, score_job
from applicant_zero.storage import get_match, initialise_database, save_match
from applicant_zero.role_priority import role_priority


def _profile(project):
    private = project / "private"
    private.mkdir(parents=True)
    resumes = {}
    for family in ("data_bi", "power_bi", "business_analysis"):
        resume = private / f"{family}.pdf"
        resume.write_text("resume", encoding="utf-8")
        resumes[family] = str(resume)
    master = private / "data_bi.docx"
    master.write_text("master", encoding="utf-8")
    (private / "candidate_profile.json").write_text(json.dumps({
        "contact": {"legal_name": "Rishi", "email": "r@example.com", "phone": "0400", "current_location": "Sydney"},
        "availability": {"full_time_from": "2026-11-15"},
        "eligibility": {"current_work_rights": "Verified", "requires_sponsorship_answer": "No"},
        "resumes": resumes,
        "editable_resume_masters": {"data_bi": str(master)},
    }), encoding="utf-8")


def test_bulk_preparation_only_uses_eligible_current_roles(tmp_path):
    project = tmp_path / "project"
    _profile(project)
    path = project / "data" / "jobs.sqlite3"
    database = initialise_database(path)
    ready = Job("ready", "Data Analyst", "Example", "Sydney", "test", "https://example.invalid/ready", "SQL and Power BI")
    review = Job("review", "Business and Process Analyst", "Example 2", "Sydney", "test", "https://example.invalid/review", "Lead the requirements gathering for our Continuous Improvement Plan. Aged care sector experience is required.")
    save_match(database, ready, score_job(ready, RISHI_PROFILE))
    save_match(database, review, score_job(review, RISHI_PROFILE))
    assert [role.external_id for role in operational_queue(path) if role.eligible_for_bulk_prepare] == ["ready"]
    prepared = prepare_eligible_roles(path)
    assert [role.external_id for role in prepared] == ["ready"]
    assert get_match(database, "ready")["workflow_status"] == "Preparing"
    assert get_match(database, "review")["workflow_status"] == "New"


def test_priority_makes_form_effort_and_evidence_gaps_visible():
    easy = role_priority({"score": 70, "recommendation": "Apply", "url": "https://jobs.lever.co/example/1", "missing_requirements": "[]"})
    hard = role_priority({"score": 70, "recommendation": "Apply", "url": "https://example.wd3.myworkdayjobs.com/job/1", "missing_requirements": "[\"clearance\"]"})
    assert easy.effort == "low"
    assert easy.score > hard.score
