from dataclasses import dataclass
import re

from .profile import CandidateProfile
from .taxonomy import classify_lane
from .eligibility import listing_eligibility_requirements


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
    lane: str | None
    matched_evidence: tuple[str, ...]
    missing_requirements: tuple[str, ...]
    reasons: tuple[str, ...]


SENIORITY_BLOCKLIST = ("senior", "lead", "principal", "manager", "director", "head of", "staff")
OUT_OF_SCOPE_TITLE_TERMS = ("data engineer", "data scientist", "machine learning", "software engineer", "software developer", "cyber security")
MISLEADING_ANALYST_TITLE_TERMS = (
    "talent", "recruitment", "human resources", "people and culture", "payroll", "actuarial",
    "credit risk", "fraud", "investments", "equity research", "seo", "digital marketing", "campaign",
)

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
    "australian citizen",
    "security clearance",
    "baseline clearance",
)

ENTRY_LEVEL_TERMS = ("graduate", "junior", "entry level", "entry-level", "early career", "0-2 years")

# These phrases signal a requirement that is substantially more specific than a
# role title.  We do not infer that Rishi has led initiatives or worked in a
# regulated care setting merely because the title is an otherwise suitable
# analyst title.  Hold these roles for a human evidence check instead of
# presenting them as ready to apply.
EVIDENCE_CHECK_PATTERNS = (
    (r"\blead(?:ing)?\s+(?:the\s+)?requirements\s+gathering\b", "independent requirements-gathering leadership"),
    (r"\b(?:aged care|home care|disability care)\s+(?:sector\s+)?experience\b", "direct care-sector experience"),
    (r"\bcontinuous improvement plan\b", "continuous-improvement delivery experience"),
)


def _direct_title_alignment(title: str, family: str) -> bool:
    """Return whether the title itself names one of the core search targets."""
    core_titles = {
        "data_bi": ("data analyst", "reporting analyst", "analytics analyst", "data and insights analyst", "data & insights analyst"),
        "power_bi": ("power bi", "business intelligence", "bi analyst"),
        "business_analysis": ("business analyst", "process analyst", "systems analyst", "business systems"),
        "it_support": ("service desk", "help desk", "it support", "technical support", "desktop support", "application support", "support analyst"),
    }
    return any(term in title for term in core_titles.get(family, ()))


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


def _evidence_gaps(description: str) -> tuple[str, ...]:
    """Return high-impact requirements that cannot safely be inferred."""
    return tuple(label for pattern, label in EVIDENCE_CHECK_PATTERNS if re.search(pattern, description))


def score_job(job: Job, profile: CandidateProfile) -> MatchResult:
    title = _normalise(job.title)
    description = _normalise(job.description)
    location = _normalise(job.location)
    text = f"{title} {description}"
    family = _role_family(title, profile)
    reasons: list[str] = []

    if not any(place in location for place in profile.locations):
        return MatchResult("Skip", 0, None, None, (), (), ("Location is outside the current Sydney, hybrid or remote policy.",))

    if family is None:
        return MatchResult("Skip", 15, None, None, (), (), ("Title is outside the approved role families.",))

    if any(term in title for term in OUT_OF_SCOPE_TITLE_TERMS):
        return MatchResult(
            "Skip", 10, None, None, (), (),
            ("Title is outside the current analytics, BI and business-analysis search focus.",),
        )

    if any(term in title for term in MISLEADING_ANALYST_TITLE_TERMS):
        return MatchResult(
            "Skip", 10, None, None, (), (),
            ("The title uses 'analyst' but is outside the selected data, BI, business-analysis and IT-support role lanes.",),
        )

    seniority_text = f"{title} {_normalise(job.seniority)}"
    if any(term in seniority_text for term in SENIORITY_BLOCKLIST):
        lane = classify_lane(job.title, job.description)
        return MatchResult("Review", 25, family, lane.identifier if lane else family, (), (), ("The role title or stated seniority appears senior; check the experience requirements before applying.",))

    required_years = _required_experience_years(description)
    if required_years is not None and required_years >= 4:
        requirement = f"{required_years}+ years of experience"
        return MatchResult(
            "Review",
            35,
            family, (classify_lane(job.title, job.description).identifier if classify_lane(job.title, job.description) else family),
            (),
            (requirement,),
            (f"The listing appears to require {requirement}; verify that your evidence supports it before applying.",),
        )

    eligibility_requirements = listing_eligibility_requirements(description)
    if eligibility_requirements:
        return MatchResult(
            "Review", 30, family, (classify_lane(job.title, job.description).identifier if classify_lane(job.title, job.description) else family), (), tuple(label for label, _ in eligibility_requirements),
            ("The role states an eligibility, citizenship or clearance condition; confirm it yourself before preparing an application.",),
        )

    evidence_gaps = _evidence_gaps(description)
    if evidence_gaps:
        return MatchResult(
            "Review",
            45,
            family,
            (classify_lane(job.title, job.description).identifier if classify_lane(job.title, job.description) else family),
            (),
            evidence_gaps,
            (
                "The listing has role-specific experience requirements that are not established by the current evidence; review them before preparing an application.",
                "Requirements to verify: " + ", ".join(evidence_gaps) + ".",
            ),
        )

    matched = tuple(skill for skill in profile.skills if skill in text)
    likely_requirements = tuple(term for term in ("azure", "aws", "snowflake", "dbt", "statistics", "agile", "jira") if term in text)
    missing_list = [requirement for requirement in likely_requirements if requirement not in profile.skills]
    if any(term in text for term in WORK_RIGHTS_TERMS):
        missing_list.append("work-rights eligibility")
    missing = tuple(missing_list)

    title_alignment = _direct_title_alignment(title, family)
    score = 55 + min(len(matched) * 4, 32) - min(len(missing) * 5, 15)
    if title_alignment:
        score += 8
        reasons.append("The title directly aligns with your selected data, BI or business-analysis search focus.")
    if any(term in text for term in ENTRY_LEVEL_TERMS):
        score += 8
        reasons.append("The role is explicitly graduate, junior or entry-level.")
    if matched:
        reasons.append("Matched evidence: " + ", ".join(matched[:6]) + ".")
    if missing:
        reasons.append("Requirements to review: " + ", ".join(missing) + ".")
    if not reasons:
        reasons.append("Role family and location match; review the detailed requirements.")

    recommendation = "Strong apply" if score >= 78 else "Apply" if score >= 62 else "Review"
    if not matched:
        recommendation = "Review"
        reasons.append("No direct skills from your verified evidence were detected; check the original description before preparing an application.")
    elif missing and recommendation == "Strong apply":
        recommendation = "Apply"
        reasons.append("A named requirement still needs checking, so this is kept as Apply rather than Strong apply.")
    resume_family = family
    if family == "adjacent_analytics":
        recommendation = "Review"
        resume_family = "data_bi"
        reasons.insert(0, "This is an adjacent analytics role; review its domain requirements before preparing an application.")
    if family == "it_support":
        recommendation = "Review"
        # An IT-support résumé will be added as a separate supported master.
        # Until then, surface the role with the closest current master rather
        # than pretending that a data résumé is already tailored for it.
        resume_family = "data_bi"
        reasons.insert(0, "This is an IT-support route. Review the technical and customer-support requirements before preparing a role-specific résumé.")
    lane = classify_lane(job.title, job.description)
    return MatchResult(recommendation, min(score, 100), resume_family, lane.identifier if lane else family, matched, missing, tuple(reasons))
