import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from .private_profile import load_profile
from .storage import get_match


def create_session_plan(database_path: Path, external_id: str) -> Path:
    with sqlite3.connect(database_path) as connection:
        job = get_match(connection, external_id)
    if job is None:
        raise ValueError("Job not found")
    profile = load_profile(database_path.parent.parent / "private" / "candidate_profile.json")
    if not profile:
        raise ValueError("Private candidate profile is not ready")
    plan = {
        "created_at": datetime.now().isoformat(timespec="minutes"),
        "job": {"title": job["title"], "company": job["company"], "url": job["url"]},
        "permitted_prefill": {
            "legal_name": profile["contact"]["legal_name"], "email": profile["contact"]["email"],
            "phone": profile["contact"]["phone"], "location": profile["contact"]["current_location"],
            "resume_path": profile["resumes"].get(job["resume_family"], ""),
            "availability": profile["availability"]["full_time_from"],
        },
        "must_stop_for": ["CAPTCHA or anti-bot check", "email or phone verification code", "password or account recovery", "unclear work-rights or sponsorship question", "final submit button"],
        "never_do": ["create an employer account password", "bypass a platform control", "submit an application without review"],
    }
    folder = database_path.parent.parent / "private" / "application_sessions"
    folder.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^a-z0-9]+", "-", f"{job['company']}-{job['title']}".lower()).strip("-")
    path = folder / f"{name}-session-plan.json"
    path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return path
