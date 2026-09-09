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
