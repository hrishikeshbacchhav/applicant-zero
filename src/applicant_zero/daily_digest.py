"""Create a local, no-cost daily list of the next job-search actions."""

import html
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .storage import initialise_database, latest_refresh_run, list_followups, list_matches


def _listing_item(row: dict) -> str:
    return (
        f"<li><a href='{html.escape(row['url'], quote=True)}'>{html.escape(row['title'])}</a> "
        f"at <strong>{html.escape(row['company'])}</strong> — {html.escape(row['recommendation'])} "
        f"(score {row['score']}; {html.escape(row['workflow_status'])})</li>"
    )


def create_daily_digest(database_path: Path) -> Path:
    """Write a private HTML digest with the most useful next actions."""
    project_root = database_path.parent.parent
    output_dir = project_root / "private"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "daily_priority_digest.html"
    with initialise_database(database_path) as connection:
        rows = list_matches(connection)
        refresh = latest_refresh_run(connection)
        followups = list_followups(connection)

    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    current = [row for row in rows if row["is_active"] and row["source"].lower() != "demo"]
    new_priority = [
        row for row in current
        if row["first_seen_at"] >= cutoff and row["recommendation"] in {"Strong apply", "Apply", "Review"}
    ][:12]
    preparing = [row for row in current if row["workflow_status"] in {"Preparing", "Saved"}][:12]
    applied = [row for row in rows if row["workflow_status"] in {"Applied", "Interview"}][:12]
    refresh_text = "No refresh has been recorded yet."
    if refresh:
        refresh_text = (
            f"{refresh['completed_at']}: {refresh['source']} collected {refresh['collected_count']} roles; "
            f"{refresh['relevant_count']} are worth reviewing. {refresh.get('detail', '')}"
        )
    section = lambda heading, items, empty: (
        f"<section><h2>{heading}</h2><ul>{''.join(_listing_item(row) for row in items) or f'<li>{empty}</li>'}</ul></section>"
    )
    followup_items = "".join(
        f"<li><a href='{html.escape(item['url'], quote=True)}'>{html.escape(item['title'])}</a> at <strong>{html.escape(item['company'])}</strong> — follow up on {html.escape(item['due_date'])}</li>"
        for item in followups
    ) or "<li>No application follow-ups are due.</li>"
    output.write_text(
        f"""<!doctype html><html><head><meta charset='utf-8'><title>Applicant Zero daily priorities</title>
<style>body{{font-family:Arial,sans-serif;max-width:900px;margin:36px auto;padding:0 20px;color:#182230;background:#f5f7fb}}h1,h2{{color:#163b67}}section{{background:#fff;border-radius:8px;padding:18px 24px;margin:16px 0;box-shadow:0 1px 4px #dce3ee}}li{{margin:10px 0;line-height:1.4}}a{{color:#1261a0}}.health{{color:#52627a}}</style></head><body>
<h1>Applicant Zero: daily priorities</h1><p class='health'>{html.escape(refresh_text)}</p>
<section><h2>Today’s order</h2><ol><li>Open the original listing for each priority role and confirm it is still suitable.</li><li>Prepare materials only for roles you want to pursue.</li><li>Record an application as Applied only after the employer site confirms submission.</li></ol></section>
{section('New roles worth reviewing', new_priority, 'No newly collected priority roles this week.')}
{section('Roles already being prepared', preparing, 'No roles are currently marked Saved or Preparing.')}
{section('Follow-ups', applied, 'No submitted applications or interviews recorded yet.')}
<section><h2>Planned application follow-ups</h2><ul>{followup_items}</ul></section>
</body></html>""",
        encoding="utf-8",
    )
    return output
