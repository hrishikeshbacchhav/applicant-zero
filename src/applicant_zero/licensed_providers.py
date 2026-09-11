"""Candidate-controlled settings for optional licensed discovery sources."""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LicensedProvider:
    identifier: str
    label: str
    enabled: bool
    max_requests_per_refresh: int
    daily_request_limit: int


def _path(project_root: Path) -> Path:
    private = project_root / "private" / "licensed_providers.json"
    local = project_root / "data" / "licensed_providers.starter.json"
    if private.exists():
        return private
    return local if local.exists() else Path(__file__).resolve().parents[2] / "data" / "licensed_providers.starter.json"


def load_licensed_providers(project_root: Path) -> tuple[LicensedProvider, ...]:
    try:
        payload = json.loads(_path(project_root).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return ()
    return tuple(
        LicensedProvider(
            identifier=str(row.get("id", "")).strip(), label=str(row.get("label", "")).strip(),
            enabled=bool(row.get("enabled", False)),
            max_requests_per_refresh=max(1, min(20, int(row.get("max_requests_per_refresh", 5)))),
            daily_request_limit=max(1, int(row.get("daily_request_limit", 20))),
        )
        for row in payload.get("providers", []) if isinstance(row, dict) and str(row.get("id", "")).strip()
    )


def enabled_licensed_providers(project_root: Path) -> tuple[LicensedProvider, ...]:
    return tuple(item for item in load_licensed_providers(project_root) if item.enabled)
