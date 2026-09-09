import json
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .private_profile import load_profile
from .resume_evidence import load_lane_resume_evidence
from .storage import get_match


DEFAULT_DRAFT_MODEL = "gpt-5.6-terra"
MAX_DRAFT_OUTPUT_TOKENS = 1_200
MAX_QUESTION_OUTPUT_TOKENS = 500
MAX_SUMMARY_WORDS = 70
MAX_COVER_LETTER_WORDS = 220
_CANDIDATE_ONLY_QUESTION = re.compile(
    r"visa|sponsor|work.?rights|citizen|permanent.?resident|gender|race|ethnic|disab|medical|injury|birth|date.?of.?birth|veteran|criminal|conviction",
    re.IGNORECASE,
)


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


def evidence_for_job(evidence: dict, lane: str | None) -> list[str]:
    """Combine global and role-lane evidence without inventing a new fact.

    Existing evidence files with only ``truthful_evidence`` remain fully
    compatible.  Candidates can optionally add lane-specific facts when a
    responsibility belongs only to one résumé direction.
    """
    facts = [str(item).strip() for item in evidence.get("truthful_evidence", []) if str(item).strip()]
    lane_facts = evidence.get("evidence_by_lane", {})
    if lane and isinstance(lane_facts, dict):
        facts.extend(str(item).strip() for item in lane_facts.get(lane, []) if str(item).strip())
    unique: list[str] = []
    seen: set[str] = set()
    for fact in facts:
        key = fact.casefold()
        if key not in seen:
            unique.append(fact)
            seen.add(key)
    return unique


def _read_job(database_path: Path, external_id: str) -> dict:
    with sqlite3.connect(database_path) as connection:
        row = get_match(connection, external_id)
    if row is None:
        raise DraftingError("Job not found.")
    return row


def _draft_path(database_path: Path, job: dict) -> Path:
    packet_directory = database_path.parent.parent / "private" / "application_packets"
    safe_name = re.sub(r"[^a-z0-9]+", "-", f"{job['company']}-{job['title']}".lower()).strip("-")
    return packet_directory / f"{safe_name}-ai-draft.json"


def _question_draft_path(database_path: Path, job: dict) -> Path:
    packet_directory = database_path.parent.parent / "private" / "application_packets"
    safe_name = re.sub(r"[^a-z0-9]+", "-", f"{job['company']}-{job['title']}".lower()).strip("-")
    return packet_directory / f"{safe_name}-question-drafts.json"


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


def load_question_drafts(database_path: Path, external_id: str) -> list[dict]:
    try:
        job = _read_job(database_path, external_id)
    except DraftingError:
        return []
    path = _question_draft_path(database_path, job)
    if not path.exists():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []


def _prompt(job: dict, evidence: dict, profile: dict) -> str:
    selected_evidence = evidence_for_job(evidence, job.get("lane"))
    resume_source = load_lane_resume_evidence(Path(profile.get("_project_root", "")), job.get("resume_family"))
    return f"""You prepare truthful job-application drafts. Use only the verified evidence provided below. Never invent a responsibility, metric, employer, date, qualification, tool, work right, or application answer. If the role asks for something unsupported, list it under unsupported_requirements.

Return valid JSON only with these keys:
- resume_summary: string, maximum 70 words
- resume_bullet_suggestions: array of up to 5 strings
- cover_letter: string, maximum 220 words
- application_answer_drafts: object with keys why_interested, relevant_experience, and availability; use "Needs confirmation" where evidence is insufficient
- unsupported_requirements: array of strings
- questions_to_confirm: array of strings

ROLE
Title: {job['title']}
Company: {job['company']}
Location: {job['location']}
Description: {job['description']}

VERIFIED EVIDENCE FOR THIS ROLE LANE
{json.dumps(selected_evidence, ensure_ascii=False)}

APPROVED RÉSUMÉ SOURCE WORDING (exact private source text; only reuse when it is truthful and relevant)
{json.dumps(resume_source, ensure_ascii=False)}

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


def _word_count(value: str) -> int:
    return len(re.findall(r"\S+", value))


def validate_ai_draft(draft: dict) -> dict:
    """Validate the bounded review format before storing it privately.

    This is a format and length gate, not a substitute for the evidence rules
    in the prompt or the candidate's final factual review.
    """
    required = {
        "resume_summary": str,
        "resume_bullet_suggestions": list,
        "cover_letter": str,
        "application_answer_drafts": dict,
        "unsupported_requirements": list,
        "questions_to_confirm": list,
    }
    if not isinstance(draft, dict) or any(not isinstance(draft.get(key), value_type) for key, value_type in required.items()):
        raise DraftingError("The drafting service returned an incomplete review format. Try again.")
    if _word_count(draft["resume_summary"]) > MAX_SUMMARY_WORDS:
        raise DraftingError("The drafting service returned a résumé summary that is too long. Try again.")
    if _word_count(draft["cover_letter"]) > MAX_COVER_LETTER_WORDS:
        raise DraftingError("The drafting service returned a cover letter that is too long. Try again.")
    bullets = draft["resume_bullet_suggestions"]
    if len(bullets) > 5 or any(not isinstance(item, str) or not item.strip() for item in bullets):
        raise DraftingError("The drafting service returned invalid résumé bullet suggestions. Try again.")
    for key in ("unsupported_requirements", "questions_to_confirm"):
        if any(not isinstance(item, str) for item in draft[key]):
            raise DraftingError("The drafting service returned an invalid review list. Try again.")
    answers = draft["application_answer_drafts"]
    expected_answers = {"why_interested", "relevant_experience", "availability"}
    if not expected_answers.issubset(answers) or any(not isinstance(answers[key], str) for key in expected_answers):
        raise DraftingError("The drafting service returned incomplete application-answer drafts. Try again.")
    return draft


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


def _usage_summary(response_data: dict) -> dict[str, int]:
    """Keep the API-reported token counts with the private draft record."""
    usage = response_data.get("usage", {})
    if not isinstance(usage, dict):
        return {}
    return {
        key: int(usage[key])
        for key in ("input_tokens", "output_tokens", "total_tokens")
        if isinstance(usage.get(key), int)
    }


def _create_response(api_key: str, payload: dict) -> dict:
    request = Request("https://api.openai.com/v1/responses", data=json.dumps(payload).encode("utf-8"), method="POST", headers={
        "Authorization": f"Bearer {api_key}", "Content-Type": "application/json"
    })
    try:
        with urlopen(request, timeout=90) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code == 401:
            raise DraftingError("OpenAI rejected the API key. Create a valid API key on the OpenAI Platform, set it in this terminal, then try again.") from error
        raise DraftingError(f"Drafting service returned HTTP {error.code}.") from error
    except URLError as error:
        raise DraftingError("Could not reach the drafting service.") from error


def create_ai_draft(database_path: Path, external_id: str, model: str | None = None) -> Path:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise DraftingError("OPENAI_API_KEY is not set on this computer.")
    project_root = database_path.parent.parent
    profile = load_profile(project_root / "private" / "candidate_profile.json")
    if not profile:
        raise DraftingError("Private candidate profile is not ready.")
    profile["_project_root"] = str(project_root)
    evidence = _load_evidence(project_root / "private" / "candidate_evidence.json")
    job = _read_job(database_path, external_id)
    model_name = model or os.environ.get("APPLICANT_ZERO_MODEL", DEFAULT_DRAFT_MODEL)
    payload = {
        "model": model_name,
        "store": False,
        "input": _prompt(job, evidence, profile),
        "text": {"verbosity": "low"},
        "max_output_tokens": MAX_DRAFT_OUTPUT_TOKENS,
    }
    response_data = _create_response(api_key, payload)
    draft = validate_ai_draft(_json_from_text(_response_text(response_data)))
    output_path = _draft_path(database_path, job)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({
        "created_at": datetime.now().isoformat(timespec="minutes"),
        "job": job["title"],
        "lane": job.get("lane"),
        "evidence_used": evidence_for_job(evidence, job.get("lane")),
        "model": model_name,
        "api_usage": _usage_summary(response_data),
        "draft": draft,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    return output_path


def create_question_draft(database_path: Path, external_id: str, question: str) -> list[dict]:
    clean_question = question.strip()
    if len(clean_question) < 8:
        raise DraftingError("Paste the full application question first.")
    if _CANDIDATE_ONLY_QUESTION.search(clean_question):
        raise DraftingError("Answer this personal eligibility or identity question directly in the employer form; Applicant Zero will not draft it.")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise DraftingError("OPENAI_API_KEY is not set on this computer.")
    project_root = database_path.parent.parent
    profile = load_profile(project_root / "private" / "candidate_profile.json")
    if not profile:
        raise DraftingError("Private candidate profile is not ready.")
    evidence = _load_evidence(project_root / "private" / "candidate_evidence.json")
    job = _read_job(database_path, external_id)
    model_name = os.environ.get("APPLICANT_ZERO_MODEL", DEFAULT_DRAFT_MODEL)
    prompt = f"""Draft one truthful response to an employer's application question. Use only the verified evidence. Do not invent achievements, dates, qualifications, tools, work rights, or other personal information. If evidence is insufficient, say so clearly.

Return valid JSON only with keys: answer (maximum 170 words), unsupported_requirement (string or empty), question_to_confirm (string or empty).

ROLE: {job['title']} at {job['company']}
QUESTION: {clean_question}
VERIFIED EVIDENCE: {json.dumps(evidence_for_job(evidence, job.get('lane')), ensure_ascii=False)}
WRITING RULES: {json.dumps(evidence.get('writing_rules', []), ensure_ascii=False)}
FULL-TIME AVAILABILITY: {profile['availability']['full_time_from']}
"""
    response_data = _create_response(api_key, {
        "model": model_name,
        "store": False,
        "input": prompt,
        "text": {"verbosity": "low"},
        "max_output_tokens": MAX_QUESTION_OUTPUT_TOKENS,
    })
    answer = _json_from_text(_response_text(response_data))
    record = {
        "created_at": datetime.now().isoformat(timespec="minutes"),
        "question": clean_question,
        "answer": str(answer.get("answer", "Needs confirmation")),
        "unsupported_requirement": str(answer.get("unsupported_requirement", "")),
        "question_to_confirm": str(answer.get("question_to_confirm", "")),
        "model": model_name,
        "api_usage": _usage_summary(response_data),
    }
    path = _question_draft_path(database_path, job)
    path.parent.mkdir(parents=True, exist_ok=True)
    drafts = load_question_drafts(database_path, external_id)
    drafts.insert(0, record)
    path.write_text(json.dumps(drafts[:20], indent=2, ensure_ascii=False), encoding="utf-8")
    return drafts
