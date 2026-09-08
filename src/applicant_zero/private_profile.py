import json
from pathlib import Path


REQUIRED_FIELDS = {
    "contact.legal_name": "legal name",
    "contact.email": "email address",
    "contact.phone": "phone number",
    "contact.current_location": "current location",
    "availability.full_time_from": "full-time availability date",
    "eligibility.current_work_rights": "current work-rights statement",
    "eligibility.requires_sponsorship_answer": "sponsorship answer",
    "resumes.data_bi": "data / BI résumé path",
    "resumes.power_bi": "Power BI résumé path",
    "resumes.business_analysis": "business analyst résumé path",
}


def _read_value(profile: dict, dotted_key: str) -> str:
    value: object = profile
    for key in dotted_key.split("."):
        if not isinstance(value, dict):
            return ""
        value = value.get(key, "")
    return str(value).strip()


def check_profile(path: Path) -> list[str]:
    if not path.exists():
        return ["Candidate profile file is missing."]
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ["Candidate profile file is not valid JSON."]

    issues = []
    for key, label in REQUIRED_FIELDS.items():
        value = _read_value(profile, key)
        if not value or value.startswith("REPLACE_"):
            issues.append(f"Add {label}.")
    for key in ("resumes.data_bi", "resumes.power_bi", "resumes.business_analysis"):
        value = _read_value(profile, key)
        if value and not value.startswith("REPLACE_") and not Path(value).expanduser().exists():
            issues.append(f"Check the file path for {_read_value(profile, key)}.")
    return issues


def load_profile(path: Path) -> dict:
    if check_profile(path):
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
