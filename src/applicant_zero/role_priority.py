"""Explainable daily ranking for roles that are already relevant."""

from dataclasses import dataclass
from datetime import datetime, timezone

from .application_routes import classify_application_url


@dataclass(frozen=True)
class RolePriority:
    score: int
    effort: str
    reasons: tuple[str, ...]


_EFFORT = {"assisted": (0, "low"), "pilot": (4, "moderate"), "login_required": (9, "high"), "complex": (11, "high"), "manual_review": (14, "high")}
_RECOMMENDATION = {"Strong apply": 20, "Apply": 12, "Review": 3}


def role_priority(row: dict, company_priority: int | None = None) -> RolePriority:
    """Rank without concealing evidence gaps or hard application work."""
    route = classify_application_url(str(row.get("url", "")))
    penalty, effort = _EFFORT[route.support_level]
    score = int(row.get("score", 0)) + _RECOMMENDATION.get(str(row.get("recommendation", "")), 0) - penalty
    reasons = [f"Role fit score {row.get('score', 0)}.", f"Application effort: {effort} ({route.platform})."]
    if company_priority:
        bonus = max(0, 6 - company_priority * 2)
        score += bonus
        reasons.append(f"Target-employer priority P{company_priority} adds {bonus} points.")
    if row.get("missing_requirements") not in (None, "[]", []):
        score -= 10
        reasons.append("Evidence or eligibility requirements need review.")
    first_seen = str(row.get("first_seen_at", ""))
    try:
        seen = datetime.fromisoformat(first_seen.replace("Z", "+00:00"))
        if seen.tzinfo is None:
            seen = seen.replace(tzinfo=timezone.utc)
        if (datetime.now(timezone.utc) - seen).days <= 3:
            score += 5
            reasons.append("Recently discovered listing.")
    except ValueError:
        pass
    return RolePriority(max(0, min(100, score)), effort, tuple(reasons))
