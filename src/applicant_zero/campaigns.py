"""Candidate-controlled discovery campaigns and their safe query budgets."""

import json
from datetime import date
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


def query_cursor_path(project_root: Path) -> Path:
    """Keep local query rotation and daily-call accounting outside Git."""
    return project_root / "private" / "discovery_query_cursor.json"


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


def _full_campaign_query_plan(project_root: Path) -> list[tuple[str, str, str]]:
    raw = _load_raw(project_root)
    locations = [str(value).strip() for value in raw.get("locations", ["Sydney", "NSW"]) if str(value).strip()]
    selected = [campaign for campaign in load_campaigns(project_root) if campaign.active and campaign.queries]
    if not selected or not locations:
        return []

    # Interleave the same query position across enabled campaigns and both
    # locations. This makes every enabled role group visible early in a capped
    # cycle rather than letting the first group consume the broad-feed budget.
    scheduled: list[tuple[str, str, str]] = []
    max_depth = max(len(campaign.queries) for campaign in selected)
    for query_index in range(max_depth):
        for location in locations:
            for campaign in selected:
                if query_index < len(campaign.queries):
                    scheduled.append((campaign.identifier, campaign.queries[query_index], location))
    return scheduled


def _configured_refresh_limit(project_root: Path, max_queries: int | None = None) -> int:
    if max_queries is not None:
        return max(0, max_queries)
    raw = _load_raw(project_root)
    return max(0, int(raw.get("max_queries_per_refresh", len(_full_campaign_query_plan(project_root)))))


def _cursor(project_root: Path) -> dict[str, int | str]:
    path = query_cursor_path(project_root)
    today = date.today().isoformat()
    try:
        cursor = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, ValueError, TypeError):
        cursor = {}
    if cursor.get("day") != today:
        return {"day": today, "offset": int(cursor.get("offset", 0) or 0), "calls_today": 0}
    return {"day": today, "offset": int(cursor.get("offset", 0) or 0), "calls_today": int(cursor.get("calls_today", 0) or 0)}


def discovery_query_status(project_root: Path, max_queries: int | None = None) -> dict[str, object]:
    """Preview the next bounded slice without consuming any API calls."""
    full_plan = _full_campaign_query_plan(project_root)
    raw = _load_raw(project_root)
    daily_limit = max(0, int(raw.get("max_queries_per_day", 60)))
    cursor = _cursor(project_root)
    remaining_today = max(0, daily_limit - int(cursor["calls_today"]))
    planned_count = min(_configured_refresh_limit(project_root, max_queries), remaining_today)
    offset = int(cursor["offset"])
    planned = [full_plan[(offset + index) % len(full_plan)] for index in range(planned_count)] if full_plan else []
    return {
        "planned": planned,
        "cycle_size": len(full_plan),
        "cycle_offset": offset % len(full_plan) if full_plan else 0,
        "daily_limit": daily_limit,
        "calls_today": int(cursor["calls_today"]),
        "remaining_today": remaining_today,
    }


def consume_discovery_query_plan(project_root: Path, attempted_queries: int) -> None:
    """Advance local rotation and account for attempted broad-feed requests."""
    attempted = max(0, attempted_queries)
    cursor = _cursor(project_root)
    cursor["offset"] = int(cursor["offset"]) + attempted
    cursor["calls_today"] = int(cursor["calls_today"]) + attempted
    path = query_cursor_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cursor, indent=2), encoding="utf-8")


def next_discovery_query_plan(project_root: Path, max_queries: int | None = None) -> list[tuple[str, str]]:
    """Return the next rotation slice; call ``consume`` after attempting it."""
    return [(query, location) for _, query, location in discovery_query_status(project_root, max_queries)["planned"]]


def _campaign_query_plan(project_root: Path, max_queries: int | None = None) -> list[tuple[str, str, str]]:
    return _full_campaign_query_plan(project_root)[:_configured_refresh_limit(project_root, max_queries)]


def save_enabled_campaigns(project_root: Path, enabled: set[str]) -> tuple[SearchCampaign, ...]:
    """Persist only candidate-selected campaign switches in the private runtime."""
    raw = _load_raw(project_root)
    for row in raw.get("campaigns", []):
        row["active"] = str(row.get("id", "")) in enabled
    path = campaign_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    return load_campaigns(project_root)
