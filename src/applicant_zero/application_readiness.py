"""Private checks that make the last application review deliberate and visible."""

from dataclasses import dataclass
from pathlib import Path

from .ai_drafting import load_ai_draft
from .application_answers import ensure_answer_library
from .private_profile import load_profile
from .resume_review import load_resume_review
from .resume_output import editable_resume_copy_exists
from .material_manifest import material_manifest_path


@dataclass(frozen=True)
class ReadinessItem:
    complete: bool
    label: str
    detail: str


def evaluate_application_readiness(database_path: Path, job: dict, materials_reviewed: bool) -> list[ReadinessItem]:
    project_root = database_path.parent.parent
    profile = load_profile(project_root / "private" / "candidate_profile.json")
    if not profile:
        return [ReadinessItem(False, "Candidate profile", "Complete the private candidate profile first.")]
    resume_path = profile.get("resumes", {}).get(job.get("resume_family"), "")
    answers = ensure_answer_library(project_root, profile).get("answers_requiring_confirmation", {})
    core_answers = ("salary_expectations", "notice_period", "linkedin_url")
    missing_answers = [key.replace("_", " ") for key in core_answers if not str(answers.get(key, "")).strip()]
    return [
        ReadinessItem(material_manifest_path(database_path, job["external_id"]) is not None, "Evidence manifest", "Role-to-evidence record is saved." if material_manifest_path(database_path, job["external_id"]) else "Create the role evidence manifest before tailoring."),
        ReadinessItem(bool(resume_path and Path(resume_path).exists()), "Approved resume", "Selected resume file is available." if resume_path and Path(resume_path).exists() else "Check the selected resume file path."),
        ReadinessItem(load_ai_draft(database_path, job["external_id"]) is not None, "AI tailoring draft", "A truthful review draft is saved."),
        ReadinessItem(load_resume_review(database_path, job["external_id"]) is not None, "Tailored resume review", "A private role-specific review page is saved."),
        ReadinessItem(editable_resume_copy_exists(database_path, job["external_id"]), "Editable role copy", "A job-specific Word copy is ready for your final edits."),
        ReadinessItem(not missing_answers, "Reusable answers", "Core answers are ready." if not missing_answers else "Still needed: " + ", ".join(missing_answers) + "."),
        ReadinessItem(materials_reviewed, "Final candidate review", "You marked the materials reviewed." if materials_reviewed else "Review the draft and mark it complete before submission."),
    ]
