import json
import re
from datetime import datetime
from pathlib import Path


CONFIRMATION_FIELDS = {
    "salary_expectations": "Salary expectations",
    "notice_period": "Notice period",
    "linkedin_url": "LinkedIn URL",
    "portfolio_url": "Portfolio URL",
    "referral_source": "How you heard about the role",
}


def _number(value: str) -> int | None:
    """Return a whole-dollar figure from Australian salary notation."""
    compact = value.lower().replace(",", "").replace("$", "").strip()
    match = re.search(r"(\d+(?:\.\d+)?)\s*(k)?", compact)
    if not match:
        return None
    amount = float(match.group(1))
    return int(amount * 1_000) if match.group(2) else int(amount)


def advertised_salary_range(description: str) -> tuple[int, int] | None:
    """Find a clearly stated annual Australian salary range, when present."""
    text = description.replace("\u2013", "-").replace("\u2014", "-")
    patterns = (
        r"\$?\s*(\d{2,3}(?:,\d{3})?|\d{2,3}\s*k)\s*(?:-|to)\s*\$?\s*(\d{2,3}(?:,\d{3})?|\d{2,3}\s*k)",
        r"between\s+\$?\s*(\d{2,3}(?:,\d{3})?|\d{2,3}\s*k)\s+and\s+\$?\s*(\d{2,3}(?:,\d{3})?|\d{2,3}\s*k)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        low, high = _number(match.group(1)), _number(match.group(2))
        if low and high and 50_000 <= low <= high <= 300_000:
            return low, high
    return None


def salary_expectation_for_job(job: dict, answers: dict) -> str:
    """Use advertised pay where available, otherwise the confirmed private fallback."""
    advertised = advertised_salary_range(str(job.get("description", "")))
    if advertised:
        low, high = advertised
        midpoint = int(round(((low + high) / 2) / 5_000) * 5_000)
        return f"AUD {midpoint:,.0f} base salary plus superannuation (negotiable)"
    return str(answers.get("answers_requiring_confirmation", {}).get("salary_expectations", "")).strip()


def ensure_answer_library(project_root: Path, profile: dict) -> dict:
    path = project_root / "private" / "application_answers.json"
    existing: dict = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
    contact = profile.get("contact", {})
    eligibility = profile.get("eligibility", {})
    availability = profile.get("availability", {})
    verified = existing.get("verified_answers", {})
    verified.update(
        {
            "full_name": contact.get("legal_name", ""),
            "email": contact.get("email", ""),
            "phone": contact.get("phone", ""),
            "current_location": contact.get("current_location", ""),
            "available_from": availability.get("full_time_from", ""),
            "current_work_rights": eligibility.get("current_work_rights", ""),
            "requires_sponsorship": eligibility.get("requires_sponsorship_answer", ""),
        }
    )
    library = {
        "updated_at": datetime.now().isoformat(timespec="minutes"),
        "verified_answers": verified,
        "answers_requiring_confirmation": existing.get(
            "answers_requiring_confirmation",
            {
                "salary_expectations": "",
                "notice_period": "",
                "linkedin_url": "",
                "portfolio_url": "",
                "referral_source": "",
            },
        ),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(library, indent=2, ensure_ascii=False), encoding="utf-8")
    return library


def save_confirmed_answer(project_root: Path, profile: dict, key: str, value: str) -> dict:
    if key not in CONFIRMATION_FIELDS:
        raise ValueError("Unknown application answer")
    library = ensure_answer_library(project_root, profile)
    library["answers_requiring_confirmation"][key] = value.strip()
    library["updated_at"] = datetime.now().isoformat(timespec="minutes")
    path = project_root / "private" / "application_answers.json"
    path.write_text(json.dumps(library, indent=2, ensure_ascii=False), encoding="utf-8")
    return library
