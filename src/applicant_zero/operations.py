"""Rank the local job queue into safe preparation work and human decisions."""

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .preparation_bundle import create_preparation_bundle
from .storage import get_match, initialise_database, list_matches, update_workflow
from .role_priority import role_priority


@dataclass(frozen=True)
class OperationalRole:
    external_id: str
    title: str
    company: str
    recommendation: str
    score: int
    workflow_status: str
    next_action: str
    blockers: tuple[str, ...]
    eligible_for_bulk_prepare: bool
    daily_priority: int
    application_effort: str


_RECOMMENDATION_WEIGHT = {"Strong apply": 3, "Apply": 2, "Review": 1}
_WORKFLOW_WEIGHT = {"New": 3, "Saved": 2, "Preparing": 1}


def operational_queue(database_path: Path, limit: int = 12) -> list[OperationalRole]:
    with initialise_database(database_path) as connection:
        rows = list_matches(connection)
    candidates = [row for row in rows if row["is_active"] and row["recommendation"] in _RECOMMENDATION_WEIGHT and row["workflow_status"] in _WORKFLOW_WEIGHT]
    candidates.sort(key=lambda row: (role_priority(row).score, _WORKFLOW_WEIGHT[row["workflow_status"]]), reverse=True)
    queue = []
    for row in candidates[:limit]:
        blockers = tuple(json.loads(row["missing_requirements"]))
        priority = role_priority(row)
        eligible = row["recommendation"] in {"Strong apply", "Apply"} and not blockers
        action = "Prepare local materials now." if eligible else "Check the listed evidence gap before preparing materials."
        if row["workflow_status"] == "Preparing":
            action = "Review the existing materials and employer form."
        queue.append(OperationalRole(row["external_id"], row["title"], row["company"], row["recommendation"], int(row["score"]), row["workflow_status"], action, blockers, eligible, priority.score, priority.effort))
    return queue


def prepare_eligible_roles(database_path: Path, limit: int = 3) -> list[OperationalRole]:
    """Create local materials only; no AI, browser or employer contact."""
    prepared = []
    for role in operational_queue(database_path, limit=limit * 4):
        if not role.eligible_for_bulk_prepare or len(prepared) >= limit:
            continue
        create_preparation_bundle(database_path, role.external_id)
        with sqlite3.connect(database_path) as connection:
            stored = get_match(connection, role.external_id)
            update_workflow(connection, role.external_id, "Preparing", str(stored.get("notes", "")) if stored else "")
        prepared.append(role)
    return prepared
