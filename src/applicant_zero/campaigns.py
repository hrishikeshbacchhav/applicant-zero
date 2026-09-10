"""Candidate-controlled discovery campaigns and their safe query budgets."""

import json
from dataclasses import dataclass
from pathlib import Path
from collections import Counter


@dataclass(frozen=True)
class SearchCampaign:
    identifier: str
    label: str
    description: str
    role_lanes: tuple[str, ...]
    queries: tuple[str, ...]
    active: bool


def _starter_path(project_root: Path) -> Path:
    local = project_root / "data" / "search_campaigns.starter.json"
    if local.exists():
        return local
    # Dashboard tests and portable runtimes point at the private state folder,
    # which deliberately contains no source files.  Fall back to the shipped
    # starter without copying it into the private runtime until the candidate
    # saves a campaign choice.
    return Path(__file__).resolve().parents[2] / "data" / "search_campaigns.starter.json"


def campaign_path(project_root: Path) -> Path:
    return project_root / "private" / "search_campaigns.json"


def _load_raw(project_root: Path) -> dict:
    private = campaign_path(project_root)
    selected = private if private.exists() else _starter_path(project_root)
    return json.loads(selected.read_text(encoding="utf-8"))


def load_campaigns(project_root: Path) -> tuple[SearchCampaign, ...]:
    raw = _load_raw(project_root)
    return tuple(
        SearchCampaign(
            identifier=str(row["id"]),
            label=str(row["label"]),
            description=str(row.get("description", "")),
            role_lanes=tuple(str(item) for item in row.get("role_lanes", [])),
            queries=tuple(str(item) for item in row.get("queries", []) if str(item).strip()),
            active=bool(row.get("active", False)),
        )
        for row in raw.get("campaigns", [])
    )


def active_lanes(project_root: Path) -> set[str]:
    return {lane for campaign in load_campaigns(project_root) if campaign.active for lane in campaign.role_lanes}


def discovery_query_plan(project_root: Path, max_queries: int | None = None) -> list[tuple[str, str]]:
    """Build a fair, controlled query plan for enabled campaigns.

    The plan alternates campaigns rather than exhausting the first one.  This
    makes a capped refresh useful when Data/BI, IT support and later campaigns
    are all active. Sydney and NSW are still queried separately so state-only
    listings are held for review instead of being silently lost.
    """
    return [(query, location) for _, query, location in _campaign_query_plan(project_root, max_queries)]


def campaign_query_allocation(project_root: Path, max_queries: int | None = None) -> dict[str, int]:
    """Return the number of broad-feed calls reserved for each active campaign."""
    return dict(Counter(identifier for identifier, _, _ in _campaign_query_plan(project_root, max_queries)))


def _campaign_query_plan(project_root: Path, max_queries: int | None = None) -> list[tuple[str, str, str]]:
    raw = _load_raw(project_root)
    locations = [str(value).strip() for value in raw.get("locations", ["Sydney", "NSW"]) if str(value).strip()]
    selected = [campaign for campaign in load_campaigns(project_root) if campaign.active and campaign.queries]
    if not selected or not locations:
        return []
    if max_queries is None:
        max_queries = int(raw.get("max_queries_per_refresh", sum(len(campaign.queries) for campaign in selected) * len(locations)))

    # Interleave the same query position across enabled campaigns and both
    # locations. With a cap, every active campaign gets an early turn.
    scheduled: list[tuple[str, str, str]] = []
    max_depth = max(len(campaign.queries) for campaign in selected)
    for query_index in range(max_depth):
        for location in locations:
            for campaign in selected:
                if query_index < len(campaign.queries):
                    scheduled.append((campaign.identifier, campaign.queries[query_index], location))
    return scheduled[:max(0, max_queries)]


def save_enabled_campaigns(project_root: Path, enabled: set[str]) -> tuple[SearchCampaign, ...]:
    """Persist only candidate-selected campaign switches in the private runtime."""
    raw = _load_raw(project_root)
    for row in raw.get("campaigns", []):
        row["active"] = str(row.get("id", "")) in enabled
    path = campaign_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    return load_campaigns(project_root)
