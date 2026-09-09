"""Validated source and target-company registries used by scheduled discovery."""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DiscoverySource:
    identifier: str
    label: str
    mode: str
    cadence: str
    role_lanes: tuple[str, ...]


@dataclass(frozen=True)
class TargetCompany:
    company: str
    sector: str
    priority: int


def _load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_sources(path: Path) -> list[DiscoverySource]:
    return [DiscoverySource(row["id"], row["label"], row["mode"], row["cadence"], tuple(row["role_lanes"])) for row in _load(path)]


def load_targets(path: Path) -> list[TargetCompany]:
    rows = [TargetCompany(row["company"], row["sector"], int(row["priority"])) for row in _load(path)]
    unique: dict[str, TargetCompany] = {}
    for item in rows:
        key = item.company.casefold()
        unique[key] = min(item, unique[key], key=lambda target: target.priority) if key in unique else item
    return sorted(unique.values(), key=lambda item: (item.priority, item.company))


def board_coverage(targets: list[TargetCompany], board_path: Path) -> dict[str, list[str]]:
    """Show which target companies have a verified public ATS board configured."""
    boards = _load(board_path)
    configured = {str(board.get("company", "")).casefold() for board in boards}
    covered = [target.company for target in targets if target.company.casefold() in configured]
    pending = [target.company for target in targets if target.company.casefold() not in configured]
    return {"configured": covered, "research_needed": pending}


def discovery_overview(sources_path: Path, targets_path: Path, board_path: Path) -> dict[str, object]:
    """Report discovery coverage without implying every target has a live vacancy."""
    sources = load_sources(sources_path)
    targets = load_targets(targets_path)
    coverage = board_coverage(targets, board_path)
    return {
        "source_count": len(sources),
        "automated_sources": [source.label for source in sources if source.mode == "public_ats_api"],
        "manual_sources": [source.label for source in sources if source.mode != "public_ats_api"],
        "target_count": len(targets),
        "configured_count": len(coverage["configured"]),
        "configured": coverage["configured"],
        "research_needed": coverage["research_needed"],
    }
