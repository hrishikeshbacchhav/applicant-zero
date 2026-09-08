from dataclasses import dataclass
import re

from .profile import CandidateProfile


@dataclass(frozen=True)
class Job:
    external_id: str
    title: str
    company: str
    location: str
    source: str
    url: str
    description: str
    seniority: str = "graduate"


@dataclass(frozen=True)
class MatchResult:
    recommendation: str
    score: int
    resume_family: str | None
    matched_evidence: tuple[str, ...]
    missing_requirements: tuple[str, ...]
    reasons: tuple[str, ...]


SENIORITY_BLOCKLIST = ("senior", "lead", "principal", "manager", "director", "head of", "staff")

EXPERIENCE_PATTERNS = (
    r"(?:minimum(?: of)?|at least|requires?|with)\s+(\d+)\+?\s+years?(?:\s+of)?\s+(?:relevant\s+|professional\s+|commercial\s+)?experience",
    r"(\d+)\+\s+years?(?:\s+of)?\s+(?:relevant\s+|professional\s+|commercial\s+)?experience",
)

WORK_RIGHTS_TERMS = (
    "unrestricted working rights",
    "unrestricted work rights",
    "full working rights",
    "no sponsorship",
    "citizen or permanent resident",
    "citizenship or permanent residency",
)


def _normalise(value: str) -> str:
    return value.lower().strip()


def _role_family(title: str, profile: CandidateProfile) -> str | None:
    title = _normalise(title)
    for family, terms in profile.role_families.items():
        if any(term in title for term in terms):
            return family
    return None


def _required_experience_years(description: str) -> int | None:
    matches: list[int] = []
    for pattern in EXPERIENCE_PATTERNS:
        matches.extend(int(value) for value in re.findall(pattern, description))
    return max(matches) if matches else None


def score_job(job: Job, profile: CandidateProfile) -> MatchResult:
    title = _normalise(job.title)
    description = _normalise(job.description)
    location = _normalise(job.location)
    text = f"{title} {description}"
    family = _role_family(title, profile)
    reasons: list[str] = []

    if not any(place in location for place in profile.locations):
        return MatchResult("Skip", 0, None, (), (), ("Location is outside the current Sydney, hybrid or remote policy.",))

    if family is None:
        return MatchResult("Skip", 15, None, (), (), ("Title is outside the approved role families.",))

    seniority_text = f"{title} {_normalise(job.seniority)}"
    if any(term in seniority_text for term in SENIORITY_BLOCKLIST):
        return MatchResult("Review", 25, family, (), (), ("The role title or stated seniority appears senior; check the experience requirements before applying.",))

    required_years = _required_experience_years(description)
    if required_years is not None and required_years >= 4:
        requirement = f"{required_years}+ years of experience"
        return MatchResult(
            "Review",
            35,
            family,
            (),
            (requirement,),
            (f"The listing appears to require {requirement}; verify that your evidence supports it before applying.",),
        )

    matched = tuple(skill for skill in profile.skills if skill in text)
    likely_requirements = tuple(term for term in ("azure", "aws", "snowflake", "dbt", "statistics", "agile", "jira") if term in text)
    missing_list = [requirement for requirement in likely_requirements if requirement not in profile.skills]
    if any(term in text for term in WORK_RIGHTS_TERMS):
        missing_list.append("work-rights eligibility")
    missing = tuple(missing_list)

    score = 55 + min(len(matched) * 4, 32) - min(len(missing) * 5, 15)
    if "graduate" in text or "junior" in text or "entry level" in text:
        score += 8
        reasons.append("The role is explicitly graduate, junior or entry-level.")
    if matched:
        reasons.append("Matched evidence: " + ", ".join(matched[:6]) + ".")
    if missing:
        reasons.append("Requirements to review: " + ", ".join(missing) + ".")
    if not reasons:
        reasons.append("Role family and location match; review the detailed requirements.")

    recommendation = "Strong apply" if score >= 78 else "Apply" if score >= 62 else "Review"
    resume_family = family
    if family == "adjacent_analytics":
        recommendation = "Review"
        resume_family = "data_bi"
        reasons.insert(0, "This is an adjacent analytics role; review its domain requirements before preparing an application.")
    return MatchResult(recommendation, min(score, 100), resume_family, matched, missing, tuple(reasons))
