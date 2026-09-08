import json
import re
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
            description TEXT NOT NULL DEFAULT '',
            recommendation TEXT NOT NULL,
            score INTEGER NOT NULL,
            resume_family TEXT,
            matched_evidence TEXT NOT NULL,
            missing_requirements TEXT NOT NULL,
            reasons TEXT NOT NULL,
            workflow_status TEXT NOT NULL DEFAULT 'New',
            notes TEXT NOT NULL DEFAULT '',
            first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER NOT NULL DEFAULT 1,
            applied_at TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS board_checks (
            company TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            job_count INTEGER NOT NULL,
            detail TEXT NOT NULL DEFAULT '',
            checked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    columns = {row[1] for row in connection.execute("PRAGMA table_info(job_matches)")}
    if "workflow_status" not in columns:
        connection.execute("ALTER TABLE job_matches ADD COLUMN workflow_status TEXT NOT NULL DEFAULT 'New'")
    if "notes" not in columns:
        connection.execute("ALTER TABLE job_matches ADD COLUMN notes TEXT NOT NULL DEFAULT ''")
    if "description" not in columns:
        connection.execute("ALTER TABLE job_matches ADD COLUMN description TEXT NOT NULL DEFAULT ''")
    migrations = {
        "first_seen_at": "TEXT NOT NULL DEFAULT ''",
        "last_seen_at": "TEXT NOT NULL DEFAULT ''",
        "is_active": "INTEGER NOT NULL DEFAULT 1",
        "applied_at": "TEXT",
        "updated_at": "TEXT NOT NULL DEFAULT ''",
    }
    for column, definition in migrations.items():
        if column not in columns:
            connection.execute(f"ALTER TABLE job_matches ADD COLUMN {column} {definition}")
    connection.execute(
        "UPDATE job_matches SET first_seen_at = CURRENT_TIMESTAMP WHERE first_seen_at = ''"
    )
    connection.execute(
        "UPDATE job_matches SET last_seen_at = CURRENT_TIMESTAMP WHERE last_seen_at = ''"
    )
    connection.execute(
        "UPDATE job_matches SET updated_at = CURRENT_TIMESTAMP WHERE updated_at = ''"
    )
    current_columns = {row[1] for row in connection.execute("PRAGMA table_info(job_matches)")}
    if {"company", "is_active"}.issubset(current_columns):
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_job_matches_company_active ON job_matches(company, is_active)"
        )
    connection.commit()
    return connection


def save_match(connection: sqlite3.Connection, job: Job, result: MatchResult) -> None:
    connection.execute(
        """
        INSERT INTO job_matches (external_id, title, company, location, source, url, description, recommendation, score, resume_family, matched_evidence, missing_requirements, reasons)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(external_id) DO UPDATE SET
            title=excluded.title, company=excluded.company, location=excluded.location,
            source=excluded.source, url=excluded.url, description=excluded.description, recommendation=excluded.recommendation,
            score=excluded.score, resume_family=excluded.resume_family,
            matched_evidence=excluded.matched_evidence, missing_requirements=excluded.missing_requirements,
            reasons=excluded.reasons, last_seen_at=CURRENT_TIMESTAMP,
            is_active=1, updated_at=CURRENT_TIMESTAMP
        """,
        (job.external_id, job.title, job.company, job.location, job.source, job.url, job.description,
         result.recommendation, result.score, result.resume_family,
         json.dumps(result.matched_evidence), json.dumps(result.missing_requirements), json.dumps(result.reasons)),
    )
    connection.commit()


def _duplicate_key(row: dict) -> str:
    values = (row["company"], row["title"], row["location"])
    return "|".join(re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip() for value in values)


def list_matches(connection: sqlite3.Connection, include_duplicates: bool = False) -> list[dict]:
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT external_id, title, company, location, source, url, description, recommendation, score,
               resume_family, matched_evidence, missing_requirements, reasons
               , workflow_status, notes, first_seen_at, last_seen_at, is_active,
               applied_at, updated_at
        FROM job_matches
        ORDER BY score DESC, company, title
        """
    ).fetchall()
    records = [dict(row) for row in rows]
    if include_duplicates:
        for record in records:
            record["duplicate_count"] = 1
        return records

    workflow_priority = {"Interview": 5, "Applied": 4, "Preparing": 3, "Saved": 2, "New": 1, "Closed": 0}
    grouped: dict[str, list[dict]] = {}
    for record in records:
        grouped.setdefault(_duplicate_key(record), []).append(record)

    deduplicated: list[dict] = []
    for duplicates in grouped.values():
        duplicates.sort(
            key=lambda row: (
                int(row["is_active"]),
                workflow_priority.get(row["workflow_status"], 0),
                int(row["score"]),
                row["last_seen_at"],
            ),
            reverse=True,
        )
        selected = duplicates[0]
        selected["duplicate_count"] = len(duplicates)
        deduplicated.append(selected)
    return sorted(deduplicated, key=lambda row: (-int(row["score"]), row["company"], row["title"]))


def get_match(connection: sqlite3.Connection, external_id: str) -> dict | None:
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        """
        SELECT external_id, title, company, location, source, url, description, recommendation, score,
               resume_family, matched_evidence, missing_requirements, reasons, workflow_status, notes,
               first_seen_at, last_seen_at, is_active, applied_at, updated_at
        FROM job_matches WHERE external_id = ?
        """,
        (external_id,),
    ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["duplicate_count"] = 1
    return result


def mark_company_jobs_inactive(
    connection: sqlite3.Connection, company: str, active_external_ids: list[str]
) -> int:
    parameters: list[object] = [company]
    exclusion = ""
    if active_external_ids:
        placeholders = ", ".join("?" for _ in active_external_ids)
        exclusion = f" AND external_id NOT IN ({placeholders})"
        parameters.extend(active_external_ids)
    cursor = connection.execute(
        """
        UPDATE job_matches
        SET is_active = 0, updated_at = CURRENT_TIMESTAMP
        WHERE company = ? AND lower(source) != 'demo' AND is_active = 1
        """ + exclusion,
        parameters,
    )
    connection.commit()
    return cursor.rowcount


def save_board_checks(connection: sqlite3.Connection, reports: list[object]) -> None:
    for report in reports:
        connection.execute(
            """
            INSERT INTO board_checks (company, status, job_count, detail, checked_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(company) DO UPDATE SET status=excluded.status, job_count=excluded.job_count,
                detail=excluded.detail, checked_at=excluded.checked_at
            """,
            (report.company, report.status, report.job_count, report.message),
        )
    connection.commit()


def list_board_checks(connection: sqlite3.Connection) -> list[dict]:
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        "SELECT company, status, job_count, detail, checked_at FROM board_checks ORDER BY company"
    ).fetchall()
    return [dict(row) for row in rows]


WORKFLOW_STATUSES = ("New", "Saved", "Preparing", "Applied", "Interview", "Closed")


def update_workflow(connection: sqlite3.Connection, external_id: str, workflow_status: str, notes: str) -> None:
    if workflow_status not in WORKFLOW_STATUSES:
        raise ValueError("Unknown workflow status")
    connection.execute(
        """
        UPDATE job_matches
        SET workflow_status = ?, notes = ?,
            applied_at = CASE
                WHEN ? = 'Applied' AND applied_at IS NULL THEN CURRENT_TIMESTAMP
                ELSE applied_at
            END,
            updated_at = CURRENT_TIMESTAMP
        WHERE external_id = ?
        """,
        (workflow_status, notes.strip(), workflow_status, external_id),
    )
    connection.commit()
