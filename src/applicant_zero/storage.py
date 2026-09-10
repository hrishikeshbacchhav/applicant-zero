import json
import re
import sqlite3
from datetime import date, timedelta
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
            lane TEXT,
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
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS board_check_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            status TEXT NOT NULL,
            job_count INTEGER NOT NULL,
            detail TEXT NOT NULL DEFAULT '',
            checked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS application_routes (
            external_id TEXT PRIMARY KEY,
            platform TEXT NOT NULL,
            support_level TEXT NOT NULL,
            apply_url TEXT NOT NULL,
            account_required INTEGER NOT NULL DEFAULT 0,
            captcha_detected INTEGER NOT NULL DEFAULT 0,
            field_count INTEGER NOT NULL DEFAULT 0,
            required_field_count INTEGER NOT NULL DEFAULT 0,
            detail TEXT NOT NULL DEFAULT '',
            checked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS application_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            external_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            status TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS application_reviews (
            external_id TEXT PRIMARY KEY,
            materials_reviewed INTEGER NOT NULL DEFAULT 0,
            review_note TEXT NOT NULL DEFAULT '',
            reviewed_at TEXT
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS application_submissions (
            external_id TEXT PRIMARY KEY,
            confirmation_reference TEXT NOT NULL DEFAULT '',
            confirmation_url TEXT NOT NULL DEFAULT '',
            submission_note TEXT NOT NULL DEFAULT '',
            submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS application_followups (
            external_id TEXT PRIMARY KEY,
            due_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Due',
            note TEXT NOT NULL DEFAULT '',
            completed_at TEXT
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS platform_pilots (
            platform TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'Not tested',
            note TEXT NOT NULL DEFAULT '',
            tested_at TEXT
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS manual_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            external_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            title TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Open',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS refresh_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            collected_count INTEGER NOT NULL,
            relevant_count INTEGER NOT NULL,
            checked_count INTEGER NOT NULL DEFAULT 0,
            unavailable_count INTEGER NOT NULL DEFAULT 0,
            detail TEXT NOT NULL DEFAULT '',
            completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS email_sync_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fetched_count INTEGER NOT NULL,
            matched_count INTEGER NOT NULL,
            updated_count INTEGER NOT NULL,
            detail TEXT NOT NULL DEFAULT '',
            completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS email_events (
            message_id TEXT PRIMARY KEY,
            received_at TEXT NOT NULL DEFAULT '',
            sender TEXT NOT NULL DEFAULT '',
            subject TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL,
            external_id TEXT,
            confidence TEXT NOT NULL DEFAULT 'unmatched',
            tracker_updated INTEGER NOT NULL DEFAULT 0,
            recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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
        "lane": "TEXT",
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
    refresh_columns = {row[1] for row in connection.execute("PRAGMA table_info(refresh_runs)")}
    if "detail" not in refresh_columns:
        connection.execute("ALTER TABLE refresh_runs ADD COLUMN detail TEXT NOT NULL DEFAULT ''")
    connection.commit()
    return connection


def save_match(connection: sqlite3.Connection, job: Job, result: MatchResult) -> None:
    connection.execute(
        """
        INSERT INTO job_matches (external_id, title, company, location, source, url, description, recommendation, score, resume_family, lane, matched_evidence, missing_requirements, reasons)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(external_id) DO UPDATE SET
            title=excluded.title, company=excluded.company, location=excluded.location,
            source=excluded.source, url=excluded.url, description=excluded.description, recommendation=excluded.recommendation,
            score=excluded.score, resume_family=excluded.resume_family, lane=excluded.lane,
            matched_evidence=excluded.matched_evidence, missing_requirements=excluded.missing_requirements,
            reasons=excluded.reasons, last_seen_at=CURRENT_TIMESTAMP,
            is_active=1, updated_at=CURRENT_TIMESTAMP
        """,
        (job.external_id, job.title, job.company, job.location, job.source, job.url, job.description,
         result.recommendation, result.score, result.resume_family, result.lane,
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
               resume_family, lane, matched_evidence, missing_requirements, reasons
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
               resume_family, lane, matched_evidence, missing_requirements, reasons, workflow_status, notes,
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


def deactivate_stale_broad_feed_jobs(connection: sqlite3.Connection, days: int = 21) -> int:
    """Hide broad-feed results that have not been seen recently.

    Company boards have an authoritative snapshot on each successful refresh.
    A broad feed is query-based, so it cannot safely make that claim each run.
    After a conservative window, untouched Adzuna listings are marked inactive
    until a later query sees them again. Candidate tracker stages are never
    changed by this maintenance step.
    """
    cursor = connection.execute(
        """
        UPDATE job_matches
        SET is_active = 0, updated_at = CURRENT_TIMESTAMP
        WHERE lower(source) = 'adzuna'
          AND is_active = 1
          AND workflow_status = 'New'
          AND last_seen_at < datetime('now', ?)
        """,
        (f"-{max(1, int(days))} days",),
    )
    connection.commit()
    return cursor.rowcount


def prune_inactive_discovery_records(connection: sqlite3.Connection, days: int = 60) -> int:
    """Remove only old, inactive, untouched discovery noise.

    The candidate's notes, preparation work, submitted applications and all
    non-New tracker stages stay intact. Imported listings are also retained.
    """
    cursor = connection.execute(
        """
        DELETE FROM job_matches
        WHERE is_active = 0
          AND workflow_status = 'New'
          AND lower(source) NOT LIKE 'imported%'
          AND last_seen_at < datetime('now', ?)
        """,
        (f"-{max(1, int(days))} days",),
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
        connection.execute(
            """
            INSERT INTO board_check_history (company, status, job_count, detail)
            VALUES (?, ?, ?, ?)
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


def list_board_check_trends(connection: sqlite3.Connection, limit: int = 30) -> tuple[dict[str, dict], list[dict]]:
    """Return per-board listing changes and a compact, auditable check history.

    A failed public endpoint is kept separate from a board that was checked and
    currently has zero listings.  This lets the dashboard explain whether a
    count changed because a role closed or because a source was unavailable.
    """
    connection.row_factory = sqlite3.Row
    rows = [dict(row) for row in connection.execute(
        """SELECT id, company, status, job_count, detail, checked_at
           FROM board_check_history ORDER BY id DESC LIMIT ?""",
        (max(1, int(limit)),),
    ).fetchall()]
    trends: dict[str, dict] = {}
    for row in rows:
        key = str(row["company"]).casefold()
        if key not in trends:
            trends[key] = {
                "company": row["company"], "status": row["status"], "job_count": row["job_count"],
                "checked_at": row["checked_at"], "previous_job_count": None, "change": None,
            }
            continue
        summary = trends[key]
        if summary["previous_job_count"] is None and row["status"] == "checked":
            # The first record encountered for a company is its current
            # observation. The next successful observation is its baseline.
            summary["previous_job_count"] = row["job_count"]
            if summary["status"] == "checked":
                summary["change"] = int(summary["job_count"]) - int(row["job_count"])
    return trends, rows


def record_refresh_run(
    connection: sqlite3.Connection,
    source: str,
    collected_count: int,
    relevant_count: int,
    checked_count: int = 0,
    unavailable_count: int = 0,
    detail: str = "",
) -> None:
    connection.execute(
        """
        INSERT INTO refresh_runs (source, collected_count, relevant_count, checked_count, unavailable_count, detail)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (source, collected_count, relevant_count, checked_count, unavailable_count, detail),
    )
    connection.commit()


def latest_refresh_run(connection: sqlite3.Connection) -> dict | None:
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        """
        SELECT source, collected_count, relevant_count, checked_count, unavailable_count, detail, completed_at
        FROM refresh_runs ORDER BY id DESC LIMIT 1
        """
    ).fetchone()
    return dict(row) if row else None


def save_email_event(
    connection: sqlite3.Connection,
    message_id: str,
    received_at: str,
    sender: str,
    subject: str,
    category: str,
    external_id: str | None,
    confidence: str,
    tracker_updated: bool,
) -> bool:
    """Record minimal mail metadata; never retain a Gmail message body locally."""
    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO email_events (
            message_id, received_at, sender, subject, category, external_id,
            confidence, tracker_updated
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (message_id, received_at[:80], sender[:300], subject[:500], category[:80], external_id, confidence[:40], int(tracker_updated)),
    )
    connection.commit()
    return cursor.rowcount > 0


def record_email_sync_run(
    connection: sqlite3.Connection,
    fetched_count: int,
    matched_count: int,
    updated_count: int,
    detail: str = "",
) -> None:
    connection.execute(
        """
        INSERT INTO email_sync_runs (fetched_count, matched_count, updated_count, detail)
        VALUES (?, ?, ?, ?)
        """,
        (fetched_count, matched_count, updated_count, detail[:1000]),
    )
    connection.commit()


def latest_email_sync_run(connection: sqlite3.Connection) -> dict | None:
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        """SELECT fetched_count, matched_count, updated_count, detail, completed_at
           FROM email_sync_runs ORDER BY id DESC LIMIT 1"""
    ).fetchone()
    return dict(row) if row else None


def list_email_events(connection: sqlite3.Connection, limit: int = 40) -> list[dict]:
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """SELECT e.message_id, e.received_at, e.sender, e.subject, e.category,
                  e.external_id, e.confidence, e.tracker_updated, e.recorded_at,
                  j.title, j.company
           FROM email_events e LEFT JOIN job_matches j ON j.external_id = e.external_id
           ORDER BY e.recorded_at DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def save_application_route(connection: sqlite3.Connection, external_id: str, route: object) -> None:
    connection.execute(
        """
        INSERT INTO application_routes (
            external_id, platform, support_level, apply_url, account_required,
            captcha_detected, field_count, required_field_count, detail, checked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(external_id) DO UPDATE SET
            platform=excluded.platform, support_level=excluded.support_level,
            apply_url=excluded.apply_url, account_required=excluded.account_required,
            captcha_detected=excluded.captcha_detected, field_count=excluded.field_count,
            required_field_count=excluded.required_field_count, detail=excluded.detail,
            checked_at=excluded.checked_at
        """,
        (
            external_id,
            route.platform,
            route.support_level,
            route.apply_url,
            int(route.account_required),
            int(route.captcha_detected),
            route.field_count,
            route.required_field_count,
            route.detail,
        ),
    )
    connection.commit()


def get_application_route(connection: sqlite3.Connection, external_id: str) -> dict | None:
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        "SELECT * FROM application_routes WHERE external_id = ?", (external_id,)
    ).fetchone()
    return dict(row) if row else None


def log_application_event(
    connection: sqlite3.Connection,
    external_id: str,
    event_type: str,
    status: str,
    detail: str = "",
) -> None:
    connection.execute(
        "INSERT INTO application_events (external_id, event_type, status, detail) VALUES (?, ?, ?, ?)",
        (external_id, event_type, status, detail[:1000]),
    )
    connection.commit()


def list_application_events(
    connection: sqlite3.Connection, external_id: str, limit: int = 10
) -> list[dict]:
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT event_type, status, detail, created_at
        FROM application_events
        WHERE external_id = ?
        ORDER BY id DESC LIMIT ?
        """,
        (external_id, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def get_material_review(connection: sqlite3.Connection, external_id: str) -> dict | None:
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        "SELECT external_id, materials_reviewed, review_note, reviewed_at FROM application_reviews WHERE external_id = ?",
        (external_id,),
    ).fetchone()
    return dict(row) if row else None


def save_material_review(connection: sqlite3.Connection, external_id: str, note: str = "") -> None:
    connection.execute(
        """
        INSERT INTO application_reviews (external_id, materials_reviewed, review_note, reviewed_at)
        VALUES (?, 1, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(external_id) DO UPDATE SET
            materials_reviewed=1, review_note=excluded.review_note, reviewed_at=CURRENT_TIMESTAMP
        """,
        (external_id, note.strip()[:1000]),
    )
    log_application_event(connection, external_id, "materials_review", "completed", "Application materials were marked reviewed by the candidate.")
    connection.commit()


def get_submission_proof(connection: sqlite3.Connection, external_id: str) -> dict | None:
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        "SELECT external_id, confirmation_reference, confirmation_url, submission_note, submitted_at FROM application_submissions WHERE external_id = ?",
        (external_id,),
    ).fetchone()
    return dict(row) if row else None


def save_submission_proof(
    connection: sqlite3.Connection,
    external_id: str,
    confirmation_reference: str,
    confirmation_url: str,
    submission_note: str,
) -> None:
    reference = confirmation_reference.strip()
    url = confirmation_url.strip()
    note = submission_note.strip()
    if not any((reference, url, note)):
        raise ValueError("Add a confirmation reference, confirmation-page link or short note before recording submission.")
    connection.execute(
        """
        INSERT INTO application_submissions (external_id, confirmation_reference, confirmation_url, submission_note, submitted_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(external_id) DO UPDATE SET
            confirmation_reference=excluded.confirmation_reference,
            confirmation_url=excluded.confirmation_url,
            submission_note=excluded.submission_note,
            submitted_at=CURRENT_TIMESTAMP
        """,
        (external_id, reference[:300], url[:1000], note[:1000]),
    )
    log_application_event(connection, external_id, "submission_proof", "recorded", "Employer submission confirmation was recorded by the candidate.")
    connection.execute(
        """
        INSERT OR IGNORE INTO application_followups (external_id, due_date)
        VALUES (?, ?)
        """,
        (external_id, _business_days_from_today(8)),
    )
    connection.commit()


def _business_days_from_today(days: int) -> str:
    current = date.today()
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current.isoformat()


def get_followup(connection: sqlite3.Connection, external_id: str) -> dict | None:
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        "SELECT external_id, due_date, status, note, completed_at FROM application_followups WHERE external_id = ?",
        (external_id,),
    ).fetchone()
    return dict(row) if row else None


def list_followups(connection: sqlite3.Connection, include_completed: bool = False) -> list[dict]:
    connection.row_factory = sqlite3.Row
    where = "" if include_completed else "WHERE f.status = 'Due'"
    rows = connection.execute(
        f"""SELECT f.external_id, f.due_date, f.status, f.note, f.completed_at,
                   j.title, j.company, j.url, j.workflow_status
            FROM application_followups f JOIN job_matches j ON j.external_id = f.external_id
            {where} ORDER BY f.due_date, j.company"""
    ).fetchall()
    return [dict(row) for row in rows]


def complete_followup(connection: sqlite3.Connection, external_id: str, note: str = "") -> None:
    connection.execute(
        """UPDATE application_followups SET status = 'Completed', note = ?, completed_at = CURRENT_TIMESTAMP
           WHERE external_id = ?""",
        (note.strip()[:1000], external_id),
    )
    log_application_event(connection, external_id, "follow_up", "completed", "Candidate completed the planned application follow-up.")
    connection.commit()


def save_manual_action(connection: sqlite3.Connection, external_id: str, kind: str, title: str, detail: str = "") -> None:
    existing = connection.execute(
        """SELECT id FROM manual_actions
           WHERE external_id = ? AND kind = ? AND title = ? AND status = 'Open'""",
        (external_id, kind.strip()[:80], title.strip()[:200]),
    ).fetchone()
    if existing:
        return
    connection.execute(
        """INSERT INTO manual_actions (external_id, kind, title, detail)
           VALUES (?, ?, ?, ?)""",
        (external_id, kind.strip()[:80], title.strip()[:200], detail.strip()[:1000]),
    )
    connection.commit()


def list_manual_actions(connection: sqlite3.Connection, include_completed: bool = False) -> list[dict]:
    connection.row_factory = sqlite3.Row
    where = "" if include_completed else "WHERE a.status = 'Open'"
    rows = connection.execute(
        f"""SELECT a.id, a.external_id, a.kind, a.title, a.detail, a.status, a.created_at,
                   j.company, j.url
            FROM manual_actions a LEFT JOIN job_matches j ON j.external_id = a.external_id
            {where} ORDER BY a.created_at DESC"""
    ).fetchall()
    return [dict(row) for row in rows]


def complete_manual_action(connection: sqlite3.Connection, action_id: int) -> None:
    connection.execute(
        "UPDATE manual_actions SET status = 'Completed', completed_at = CURRENT_TIMESTAMP WHERE id = ?",
        (action_id,),
    )
    connection.commit()


def list_platform_pilots(connection: sqlite3.Connection) -> list[dict]:
    connection.row_factory = sqlite3.Row
    rows = connection.execute("SELECT platform, status, note, tested_at FROM platform_pilots ORDER BY platform").fetchall()
    return [dict(row) for row in rows]


def save_platform_pilot(connection: sqlite3.Connection, platform: str, status: str, note: str = "") -> None:
    if status not in {"Passed supervised pilot", "Manual only", "Unavailable"}:
        raise ValueError("Unknown pilot status")
    connection.execute(
        """INSERT INTO platform_pilots (platform, status, note, tested_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(platform) DO UPDATE SET status=excluded.status, note=excluded.note, tested_at=CURRENT_TIMESTAMP""",
        (platform, status, note.strip()[:1000]),
    )
    connection.commit()


# Keep outcomes separate from a generic closed state so the local tracker can
# report the job-search funnel accurately without inferring employer feedback.
WORKFLOW_STATUSES = ("New", "Saved", "Preparing", "Applied", "Interview", "Offer", "Rejected", "Closed")


def update_workflow(connection: sqlite3.Connection, external_id: str, workflow_status: str, notes: str) -> None:
    if workflow_status not in WORKFLOW_STATUSES:
        raise ValueError("Unknown workflow status")
    previous = connection.execute(
        "SELECT workflow_status FROM job_matches WHERE external_id = ?", (external_id,)
    ).fetchone()
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
    if previous and previous[0] != workflow_status:
        connection.execute(
            "INSERT INTO application_events (external_id, event_type, status, detail) VALUES (?, 'tracker', ?, ?)",
            (
                external_id,
                workflow_status,
                f"Tracker changed from {previous[0]} to {workflow_status}.",
            ),
        )
    connection.commit()
