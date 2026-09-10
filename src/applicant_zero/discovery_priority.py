"""Rank discovery work without treating a target employer as a live vacancy."""

from dataclasses import dataclass

from .discovery_registry import TargetCompany


@dataclass(frozen=True)
class DiscoveryPriority:
    company: str
    sector: str
    priority: int
    route: str
    health: str
    action: str
    score: int


def prioritise_targets(targets: list[TargetCompany], coverage_rows: list[dict[str, object]]) -> list[DiscoveryPriority]:
    """Put healthy, configured priority employers first and make gaps visible."""
    coverage = {str(row["company"]).casefold(): row for row in coverage_rows}
    ranked: list[DiscoveryPriority] = []
    for target in targets:
        row = coverage.get(target.company.casefold(), {})
        route = str(row.get("route", "Research queue"))
        health = str(row.get("health", "not checked"))
        configured = route == "Public ATS refresh"
        score = (40 - target.priority * 8) + (30 if configured else 0)
        if health == "checked":
            score += 20
            action = "Automatic refresh is healthy. Review relevant current roles."
        elif configured and health in {"stale", "not checked"}:
            score += 8
            action = "Refresh this configured board before relying on its queue."
        elif configured and health == "unavailable":
            action = "Keep the saved roles, then retry this public board later."
        else:
            action = "Research a public careers route or add a suitable listing manually."
        ranked.append(DiscoveryPriority(target.company, target.sector, target.priority, route, health, action, score))
    return sorted(ranked, key=lambda item: (-item.score, item.priority, item.company))
