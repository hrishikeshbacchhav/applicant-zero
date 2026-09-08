from dataclasses import dataclass

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


SENIORITY_BLOCKLIST = ("senior", "lead", "principal", "manager", "director", "5+ years", "7+ years")


def _normalise(value: str) -> str:
    return value.lower().strip()


def _role_family(title: str, profile: CandidateProfile) -> str | None:
    title = _normalise(title)
    for family, terms in profile.role_families.items():
        if any(term in title for term in terms):
            return family
    return None


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
        return MatchResult("Review", 25, family, (), (), ("The description may require senior-level experience; check the stated minimum requirements.",))

    matched = tuple(skill for skill in profile.skills if skill in text)
    likely_requirements = tuple(term for term in ("azure", "aws", "snowflake", "dbt", "statistics", "agile", "jira") if term in text)
    missing = tuple(requirement for requirement in likely_requirements if requirement not in profile.skills)

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
