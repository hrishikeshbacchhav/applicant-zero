"""Re-evaluate locally stored discovery records when search focus changes."""

import sqlite3

from .profile import RISHI_PROFILE
from .scoring import Job, score_job
from .storage import list_inventory_records, save_match


def rescore_active_inventory(connection: sqlite3.Connection, enabled_lanes: set[str]) -> dict[str, int]:
    """Apply the campaign selection to existing active raw records locally."""
    records = list_inventory_records(connection)
    relevant = 0
    for row in records:
        job = Job(
            external_id=str(row["external_id"]), title=str(row["title"]),
            company=str(row["company"]), location=str(row["location"]),
            source=str(row["source"]), url=str(row["url"]),
            description=str(row["description"]),
        )
        result = score_job(job, RISHI_PROFILE, enabled_lanes)
        save_match(connection, job, result)
        relevant += result.recommendation != "Skip"
    return {"rescored": len(records), "relevant": relevant}
