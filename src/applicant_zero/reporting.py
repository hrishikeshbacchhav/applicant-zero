"""Private export helpers for the job-search tracker."""

import csv
import io
import sqlite3
from pathlib import Path

from .storage import initialise_database, list_followups, list_matches


def tracker_csv(database_path: Path) -> str:
    with initialise_database(database_path) as connection:
        jobs = list_matches(connection, include_duplicates=True)
        followups = {item["external_id"]: item for item in list_followups(connection, include_completed=True)}
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=[
        "role", "company", "location", "source", "listing_url", "recommendation", "score",
        "resume_family", "tracker_status", "first_seen", "last_seen", "applied_at", "active",
        "follow_up_due", "follow_up_status", "notes",
    ])
    writer.writeheader()
    for job in jobs:
        followup = followups.get(job["external_id"], {})
        writer.writerow({
            "role": job["title"], "company": job["company"], "location": job["location"],
            "source": job["source"], "listing_url": job["url"], "recommendation": job["recommendation"],
            "score": job["score"], "resume_family": job["resume_family"] or "", "tracker_status": job["workflow_status"],
            "first_seen": job["first_seen_at"], "last_seen": job["last_seen_at"], "applied_at": job["applied_at"] or "",
            "active": "Yes" if job["is_active"] else "No", "follow_up_due": followup.get("due_date", ""),
            "follow_up_status": followup.get("status", ""), "notes": job["notes"],
        })
    return output.getvalue()
