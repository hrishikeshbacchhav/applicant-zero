"""Create an auditable role-to-material evidence manifest before editing a resume."""

import hashlib
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from .private_profile import load_profile
from .resume_evidence import inventory_path, load_lane_resume_evidence
from .eligibility import evaluate_listing_eligibility
from .storage import get_match
from .job_intelligence import inspect_job


def _path(database_path: Path, row: dict) -> Path:
    safe = re.sub(r"[^a-z0-9]+", "-", f"{row['company']}-{row['title']}".lower()).strip("-")
    return database_path.parent.parent / "private" / "application_packets" / f"{safe}-material-manifest.json"


def create_material_manifest(database_path: Path, external_id: str) -> Path:
    """Save the facts and checks that may support a role-specific edit."""
    with sqlite3.connect(database_path) as connection:
        row = get_match(connection, external_id)
    if row is None:
        raise ValueError("Job not found.")
    profile = load_profile(database_path.parent.parent / "private" / "candidate_profile.json")
    if not profile:
        raise ValueError("Private candidate profile is not ready.")
    family = str(row.get("resume_family") or "")
    resume = Path(profile.get("resumes", {}).get(family, ""))
    master = Path(profile.get("editable_resume_masters", {}).get(family, ""))
    description = str(row.get("description", ""))
    intelligence = inspect_job(str(row["title"]), str(row["location"]), description)
    eligibility_check = evaluate_listing_eligibility(description, profile)
    fingerprint = hashlib.sha256(f"{row['url']}\n{description}".encode("utf-8")).hexdigest()[:16]
    payload = {
        "schema_version": 1,
        "created_at": datetime.now().isoformat(timespec="minutes"),
        "job": {
            "external_id": external_id,
            "title": row["title"],
            "company": row["company"],
            "location": row["location"],
            "listing_url": row["url"],
            "listing_fingerprint": fingerprint,
        },
        "resume_route": {
            "family": family or None,
            "approved_pdf": str(resume) if resume.exists() else "",
            "editable_master": str(master) if master.exists() else "",
            "private_evidence_inventory": str(inventory_path(database_path.parent.parent)) if inventory_path(database_path.parent.parent).exists() else "",
            "extracted_source_lines_available": len(load_lane_resume_evidence(database_path.parent.parent, family)),
        },
        "evidence": {
            "matched": json.loads(row["matched_evidence"]),
            "requirements_to_check": json.loads(row["missing_requirements"]),
            "recommendation_reasons": json.loads(row["reasons"]),
        },
        "listing_intelligence": {
            "salary": intelligence.salary,
            "contacts": intelligence.contacts,
            "closing_detail": intelligence.closing_detail,
            "employment_type": intelligence.employment_type,
            "location_signal": intelligence.location_signal,
        },
        "eligibility_review": {
            "outcome": eligibility_check.outcome,
            "requirements": eligibility_check.requirements,
            "detail": eligibility_check.detail,
        },
        "editing_rules": [
            "Keep employers, dates, qualifications, tools, responsibilities and metrics truthful.",
            "Use only matched evidence or evidence verified separately in the private evidence library.",
            "Do not remove an important factual role merely to imitate a job description.",
            "Compare the final PDF with the original listing before upload.",
        ],
        "next_actions": [
            "Use the matched evidence to decide what belongs in the summary and bullet wording.",
            "Resolve every listed requirement before claiming it in a resume or response.",
        "Generate an AI review draft only after the private evidence library is current.",
        "Do not continue if the eligibility review is blocked; otherwise verify each condition in the employer form.",
        ],
    }
    path = _path(database_path, row)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def material_manifest_path(database_path: Path, external_id: str) -> Path | None:
    with sqlite3.connect(database_path) as connection:
        row = get_match(connection, external_id)
    if row is None:
        return None
    path = _path(database_path, row)
    return path if path.exists() else None
