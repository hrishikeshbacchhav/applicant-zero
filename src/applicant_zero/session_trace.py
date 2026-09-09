"""Private, append-only traces for supervised browser application sessions."""

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from .storage import get_match


def _trace_path(database_path: Path, external_id: str) -> Path:
    safe = re.sub(r"[^a-z0-9]+", "-", external_id.lower()).strip("-") or "application"
    return database_path.parent.parent / "private" / "application_sessions" / f"{safe}-trace.json"


def start_trace(database_path: Path, external_id: str, platform: str, apply_url: str) -> Path:
    with sqlite3.connect(database_path) as connection:
        job = get_match(connection, external_id)
    if job is None:
        raise ValueError("Job not found.")
    path = _trace_path(database_path, external_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "external_id": external_id,
        "job": {"title": job["title"], "company": job["company"]},
        "platform": platform,
        "apply_url": apply_url,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "events": [],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def append_trace(database_path: Path, external_id: str, event: str, detail: str = "", page_url: str = "", screenshot: str = "") -> Path:
    path = _trace_path(database_path, external_id)
    if not path.exists():
        raise ValueError("Application trace has not started.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.setdefault("events", []).append({
        "at": datetime.now().isoformat(timespec="seconds"),
        "event": event,
        "detail": detail[:1000],
        "page_url": page_url,
        "screenshot": screenshot,
    })
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def capture_handoff_screenshot(database_path: Path, external_id: str, page, label: str) -> str:
    """Save a private screenshot when Playwright can capture one; never fail a session for it."""
    folder = database_path.parent.parent / "private" / "application_sessions" / "screenshots"
    folder.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^a-z0-9]+", "-", f"{external_id}-{label}".lower()).strip("-")
    path = folder / f"{safe}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
    try:
        page.screenshot(path=str(path), full_page=False)
    except Exception:
        return ""
    return str(path)


def load_trace(database_path: Path, external_id: str) -> dict | None:
    path = _trace_path(database_path, external_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
