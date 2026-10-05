"""Private, source-specific cadence records for documented public feeds."""

import json
from datetime import date
from pathlib import Path


def _path(state: Path) -> Path:
    return state / "private" / "source_schedule.json"


def _load(state: Path) -> dict[str, str]:
    path = _path(state)
    try:
        payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, ValueError, TypeError):
        return {}
    return {str(key): str(value) for key, value in payload.items()} if isinstance(payload, dict) else {}


def due_today(state: Path, source: str, *, today: date | None = None) -> bool:
    """Return whether a daily-cached public source can be queried today."""
    day = (today or date.today()).isoformat()
    return _load(state).get(source.strip().casefold()) != day


def record_attempt(state: Path, source: str, *, today: date | None = None) -> None:
    """Record one source attempt so a manual retry cannot defeat its cadence."""
    path = _path(state)
    payload = _load(state)
    payload[source.strip().casefold()] = (today or date.today()).isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
