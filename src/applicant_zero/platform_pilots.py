import html
import sqlite3
from pathlib import Path

from .storage import initialise_database, list_platform_pilots


PLATFORMS = (
    ("Lever", "Direct hosted form; safe-field browser assistance is available."),
    ("Greenhouse", "Hosted form; test each employer form before relying on assistance."),
    ("SEEK", "Candidate login handoff; you sign in yourself before any safe-field assistance."),
    ("LinkedIn", "Candidate login handoff; you sign in yourself before any safe-field assistance."),
    ("Workday", "Complex multi-step form; treat as supervised manual review until a real pilot passes."),
    ("Ashby", "Hosted form; test a real employer form before relying on assistance."),
)


def build_platform_pilots_page(database_path: Path) -> str:
    with initialise_database(database_path) as connection:
        records = {item["platform"]: item for item in list_platform_pilots(connection)}
    rows = "".join(
        f"<tr><td><strong>{html.escape(platform)}</strong><small>{html.escape(detail)}</small></td>"
        f"<td>{html.escape(records.get(platform, {}).get('status', 'Not tested'))}</td>"
        f"<td>{html.escape(records.get(platform, {}).get('note', ''))}</td>"
        f"<td><form method='post' action='/platform-pilot'><input type='hidden' name='platform' value='{html.escape(platform, quote=True)}'>"
        f"<select name='status'><option>Passed supervised pilot</option><option>Manual only</option><option>Unavailable</option></select>"
        f"<input name='note' placeholder='What happened?'><button>Save result</button></form></td></tr>"
        for platform, detail in PLATFORMS
    )
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>Applicant Zero platform pilots</title><style>body{{font-family:Arial,sans-serif;max-width:1200px;margin:36px auto;padding:0 20px;background:#f5f7fb;color:#182230}}h1{{color:#163b67}}table{{width:100%;border-collapse:collapse;background:#fff}}th,td{{padding:14px;border-bottom:1px solid #dce3ee;text-align:left;vertical-align:top}}small{{display:block;color:#667085;margin-top:5px}}select,input,button{{padding:8px;margin:3px;border:1px solid #c7d2e3;border-radius:5px}}button{{background:#163b67;color:#fff}}a{{color:#1261a0;font-weight:bold}}</style></head><body><p><a href='/'>← Return to job queue</a></p><h1>Supervised platform pilots</h1><p>Only record a result after using a real application form. Do not enter passwords, solve CAPTCHAs, or submit an application through this page.</p><table><thead><tr><th>Platform</th><th>Current result</th><th>Notes</th><th>Record actual test</th></tr></thead><tbody>{rows}</tbody></table></body></html>"""
