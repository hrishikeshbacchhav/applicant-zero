"""Small local checks that make daily operation easier to trust."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .private_profile import check_profile
from .storage import initialise_database, latest_refresh_run


def health_report(project_root: Path) -> list[tuple[str, bool, str]]:
    database_path = project_root / "data" / "applicant_zero.sqlite3"
    profile_issues = check_profile(project_root / "private" / "candidate_profile.json")
    database_ok = True
    refresh_detail = "No discovery refresh has been recorded yet."
    try:
        with initialise_database(database_path) as connection:
            refresh = latest_refresh_run(connection)
        if refresh:
            refresh_detail = f"Last refresh: {refresh['completed_at']} ({refresh['source']})."
    except sqlite3.Error as error:
        database_ok = False
        refresh_detail = f"Database check failed: {error}"
    return [
        ("Private candidate profile", not profile_issues, "Ready." if not profile_issues else " ".join(profile_issues)),
        ("Local database", database_ok, "Ready." if database_ok else refresh_detail),
        ("Discovery refresh", database_ok, refresh_detail),
        ("Private backups", True, "Use scripts\\backup_private_data.ps1 whenever you want a dated local copy."),
    ]


def health_page(project_root: Path) -> str:
    rows = health_report(project_root)
    items = "".join(
        f"<li class='{'ok' if healthy else 'issue'}'><strong>{label}:</strong> {detail}</li>"
        for label, healthy, detail in rows
    )
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>Applicant Zero system health</title><style>body{{font-family:Arial,sans-serif;max-width:800px;margin:40px auto;padding:0 20px;background:#f5f7fb;color:#182230}}h1{{color:#163b67}}section{{background:#fff;border-radius:8px;padding:20px;box-shadow:0 1px 4px #dce3ee}}li{{margin:14px 0}}.ok{{color:#12643b}}.issue{{color:#8a5a00}}a{{color:#1261a0;font-weight:bold}}</style></head><body><p><a href='/'>← Return to job queue</a></p><h1>System health</h1><section><ul>{items}</ul></section><p>Checked {generated}. Applicant Zero runs locally on this computer; it does not require cloud hosting for the current workflow.</p></body></html>"""
