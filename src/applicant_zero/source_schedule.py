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


def _board_cursor_path(state: Path) -> Path:
    return state / "private" / "board_refresh_cursor.json"


def rotating_board_batch(state: Path, boards: list[dict], limit: int) -> list[dict]:
    """Choose the next fair slice of public boards for a scheduled refresh.

    A growing direct-employer registry should be refreshed broadly without
    hitting every employer endpoint three times a day.  The cursor is private
    local state; it advances only after a selection, and wraps cleanly when
    every board has had a turn.  Explicit ``--company-boards`` collection is
    intentionally still able to read the whole supplied file.
    """
    if not boards or limit <= 0:
        return []
    path = _board_cursor_path(state)
    try:
        payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        cursor = int(payload.get("cursor", 0)) if isinstance(payload, dict) else 0
    except (OSError, ValueError, TypeError):
        cursor = 0
    count = len(boards)
    cursor %= count
    size = min(limit, count)
    selected = [boards[(cursor + offset) % count] for offset in range(size)]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"cursor": (cursor + size) % count}, indent=2), encoding="utf-8")
    return selected
