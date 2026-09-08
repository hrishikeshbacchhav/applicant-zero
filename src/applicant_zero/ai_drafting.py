import json
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .private_profile import load_profile
from .storage import list_matches


class DraftingError(Exception):
    pass


def check_tailoring_setup(project_root: Path) -> list[str]:
    issues: list[str] = []
    profile = load_profile(project_root / "private" / "candidate_profile.json")
    if not profile:
        issues.append("Private candidate profile is not ready.")
    try:
        _load_evidence(project_root / "private" / "candidate_evidence.json")
    except DraftingError as error:
        issues.append(str(error))
    if not os.environ.get("OPENAI_API_KEY"):
        issues.append("OPENAI_API_KEY is not set for this terminal session.")
    return issues


def _load_evidence(path: Path) -> dict:
    if not path.exists():
        raise DraftingError("Private evidence library is missing.")
    try:
        evidence = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise DraftingError("Private evidence library is not valid JSON.") from error
    facts = evidence.get("truthful_evidence", [])
    if not facts or any(str(fact).startswith("Replace this") for fact in facts):
        raise DraftingError("Private evidence library needs verified evidence before drafting.")
    return evidence


def _read_job(database_path: Path, external_id: str) -> dict:
    with sqlite3.connect(database_path) as connection:
        rows = [row for row in list_matches(connection) if row["external_id"] == external_id]
    if not rows:
        raise DraftingError("Job not found.")
    return rows[0]


def _draft_path(database_path: Path, job: dict) -> Path:
    packet_directory = database_path.parent.parent / "private" / "application_packets"
    safe_name = re.sub(r"[^a-z0-9]+", "-", f"{job['company']}-{job['title']}".lower()).strip("-")
    return packet_directory / f"{safe_name}-ai-draft.json"


def load_ai_draft(database_path: Path, external_id: str) -> dict | None:
    try:
        job = _read_job(database_path, external_id)
    except DraftingError:
        return None
    path = _draft_path(database_path, job)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _prompt(job: dict, evidence: dict, profile: dict) -> str:
    return f"""You prepare truthful job-application drafts. Use only the verified evidence provided below. Never invent a responsibility, metric, employer, date, qualification, tool, work right, or application answer. If the role asks for something unsupported, list it under unsupported_requirements.

Return valid JSON only with these keys:
- resume_summary: string, maximum 70 words
- resume_bullet_suggestions: array of up to 5 strings
- cover_letter: string, maximum 220 words
- unsupported_requirements: array of strings
- questions_to_confirm: array of strings

ROLE
Title: {job['title']}
Company: {job['company']}
Location: {job['location']}
Description: {job['description']}

VERIFIED EVIDENCE
{json.dumps(evidence['truthful_evidence'], ensure_ascii=False)}

WRITING RULES
{json.dumps(evidence.get('writing_rules', []), ensure_ascii=False)}

CONFIRMED AVAILABILITY
{profile['availability']['full_time_from']}
"""


def _json_from_text(text: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as error:
        start = cleaned.find("{")
        if start >= 0:
            try:
                value, _ = json.JSONDecoder().raw_decode(cleaned[start:])
                return value
            except json.JSONDecodeError:
                pass
        raise DraftingError("The drafting service returned an invalid format. Try again.") from error


def _response_text(response_data: dict) -> str:
    direct_text = response_data.get("output_text")
    if isinstance(direct_text, str) and direct_text.strip():
        return direct_text
    parts: list[str] = []
    for item in response_data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                parts.append(content["text"])
    return "\n".join(parts)


def create_ai_draft(database_path: Path, external_id: str, model: str | None = None) -> Path:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise DraftingError("OPENAI_API_KEY is not set on this computer.")
    profile = load_profile(database_path.parent.parent / "private" / "candidate_profile.json")
    if not profile:
        raise DraftingError("Private candidate profile is not ready.")
    evidence = _load_evidence(database_path.parent.parent / "private" / "candidate_evidence.json")
    job = _read_job(database_path, external_id)
    payload = json.dumps({
        "model": model or os.environ.get("APPLICANT_ZERO_MODEL", "gpt-5.5"),
        "store": False,
        "input": _prompt(job, evidence, profile),
        "text": {"verbosity": "low"},
    }).encode("utf-8")
    request = Request("https://api.openai.com/v1/responses", data=payload, method="POST", headers={
        "Authorization": f"Bearer {api_key}", "Content-Type": "application/json"
    })
    try:
        with urlopen(request, timeout=90) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code == 401:
            raise DraftingError("OpenAI rejected the API key. Create a valid API key on the OpenAI Platform, set it in this terminal, then try again.") from error
        raise DraftingError(f"Drafting service returned HTTP {error.code}.") from error
    except URLError as error:
        raise DraftingError("Could not reach the drafting service.") from error
    draft = _json_from_text(_response_text(response_data))
    output_path = _draft_path(database_path, job)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({"created_at": datetime.now().isoformat(timespec="minutes"), "job": job["title"], "draft": draft}, indent=2, ensure_ascii=False), encoding="utf-8")
    return output_path
