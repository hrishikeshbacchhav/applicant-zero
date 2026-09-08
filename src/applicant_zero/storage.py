import json
import sqlite3
from pathlib import Path

from .scoring import Job, MatchResult


def initialise_database(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS job_matches (
            external_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT NOT NULL,
            source TEXT NOT NULL,
            url TEXT NOT NULL,
            recommendation TEXT NOT NULL,
            score INTEGER NOT NULL,
            resume_family TEXT,
            matched_evidence TEXT NOT NULL,
            missing_requirements TEXT NOT NULL,
            reasons TEXT NOT NULL,
            workflow_status TEXT NOT NULL DEFAULT 'New',
            notes TEXT NOT NULL DEFAULT ''
        )
        """
    )
    columns = {row[1] for row in connection.execute("PRAGMA table_info(job_matches)")}
    if "workflow_status" not in columns:
        connection.execute("ALTER TABLE job_matches ADD COLUMN workflow_status TEXT NOT NULL DEFAULT 'New'")
    if "notes" not in columns:
        connection.execute("ALTER TABLE job_matches ADD COLUMN notes TEXT NOT NULL DEFAULT ''")
    connection.commit()
    return connection


def save_match(connection: sqlite3.Connection, job: Job, result: MatchResult) -> None:
    connection.execute(
        """
        INSERT INTO job_matches (external_id, title, company, location, source, url, recommendation, score, resume_family, matched_evidence, missing_requirements, reasons)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(external_id) DO UPDATE SET
            title=excluded.title, company=excluded.company, location=excluded.location,
            source=excluded.source, url=excluded.url, recommendation=excluded.recommendation,
            score=excluded.score, resume_family=excluded.resume_family,
            matched_evidence=excluded.matched_evidence, missing_requirements=excluded.missing_requirements,
            reasons=excluded.reasons
        """,
        (job.external_id, job.title, job.company, job.location, job.source, job.url,
         result.recommendation, result.score, result.resume_family,
         json.dumps(result.matched_evidence), json.dumps(result.missing_requirements), json.dumps(result.reasons)),
    )
    connection.commit()


def list_matches(connection: sqlite3.Connection) -> list[dict]:
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT external_id, title, company, location, source, url, recommendation, score,
               resume_family, matched_evidence, missing_requirements, reasons
               , workflow_status, notes
        FROM job_matches
        ORDER BY score DESC, company, title
        """
    ).fetchall()
    return [dict(row) for row in rows]


WORKFLOW_STATUSES = ("New", "Saved", "Preparing", "Applied", "Interview", "Closed")


def update_workflow(connection: sqlite3.Connection, external_id: str, workflow_status: str, notes: str) -> None:
    if workflow_status not in WORKFLOW_STATUSES:
        raise ValueError("Unknown workflow status")
    connection.execute(
        "UPDATE job_matches SET workflow_status = ?, notes = ? WHERE external_id = ?",
        (workflow_status, notes.strip(), external_id),
    )
    connection.commit()
