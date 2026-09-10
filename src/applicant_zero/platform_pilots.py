import html
import json
import sqlite3
from collections import Counter
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


def form_knowledge(database_path: Path) -> dict[str, list[dict]]:
    """Summarise privacy-safe form structures recorded during real pilots.

    The browser trace contains labels, control types and handling categories,
    never the candidate's typed values.  Aggregating those descriptors makes
    repeated hosted forms easier to understand without turning personal
    answers into a shared data set.
    """
    folder = database_path.parent.parent / "private" / "application_sessions"
    grouped: dict[str, Counter[tuple[str, str, str]]] = {}
    if not folder.exists():
        return {}
    for trace_path in folder.glob("*-trace.json"):
        try:
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        platform = str(trace.get("platform", "Unknown")).strip() or "Unknown"
        counter = grouped.setdefault(platform, Counter())
        # Keep a field once per trace.  One repeated page during a session must
        # not make a question look more common than it actually is.
        seen: set[tuple[str, str, str]] = set()
        for page in trace.get("form_pages", []):
            for field in page.get("fields", []):
                label = " ".join(str(field.get("label", "")).split()).lower()[:220]
                control = str(field.get("control", "")).lower()[:40]
                handling = str(field.get("handling", "candidate review")).lower()[:40]
                if label and control:
                    seen.add((label, control, handling))
        counter.update(seen)
    return {
        platform: [
            {"label": label, "control": control, "handling": handling, "seen_in_sessions": count}
            for (label, control, handling), count in counter.most_common()
        ]
        for platform, counter in sorted(grouped.items())
    }


def build_platform_pilots_page(database_path: Path) -> str:
    with initialise_database(database_path) as connection:
        records = {item["platform"]: item for item in list_platform_pilots(connection)}
    knowledge = form_knowledge(database_path)
    rows = "".join(
        f"<tr><td><strong>{html.escape(platform)}</strong><small>{html.escape(detail)}</small></td>"
        f"<td>{html.escape(records.get(platform, {}).get('status', 'Not tested'))}</td>"
        f"<td>{html.escape(records.get(platform, {}).get('note', ''))}</td>"
        f"<td><form method='post' action='/platform-pilot'><input type='hidden' name='platform' value='{html.escape(platform, quote=True)}'>"
        f"<select name='status'><option>Passed supervised pilot</option><option>Manual only</option><option>Unavailable</option></select>"
        f"<input name='note' placeholder='What happened?'><button>Save result</button></form></td></tr>"
        for platform, detail in PLATFORMS
    )
    knowledge_sections = "".join(
        "<article><h3>" + html.escape(platform) + "</h3><ul>" + "".join(
            f"<li><strong>{html.escape(field['label'])}</strong> · {html.escape(field['control'])} · {html.escape(field['handling'])} · seen in {field['seen_in_sessions']} session(s)</li>"
            for field in fields
        ) + "</ul></article>"
        for platform, fields in knowledge.items()
    ) or "<p class='muted'>No completed assisted form structures have been recorded yet. They appear here after a supervised browser session reaches a form page.</p>"
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>Applicant Zero platform pilots</title><style>body{{font-family:Arial,sans-serif;max-width:1200px;margin:36px auto;padding:0 20px;background:#f5f7fb;color:#182230}}h1,h2,h3{{color:#163b67}}table{{width:100%;border-collapse:collapse;background:#fff}}th,td{{padding:14px;border-bottom:1px solid #dce3ee;text-align:left;vertical-align:top}}small,.muted{{display:block;color:#667085;margin-top:5px}}select,input,button{{padding:8px;margin:3px;border:1px solid #c7d2e3;border-radius:5px}}button{{background:#163b67;color:#fff}}a{{color:#1261a0;font-weight:bold}}section,article{{background:#fff;border-radius:8px;padding:16px;margin:20px 0;box-shadow:0 1px 4px #dce3ee}}li{{margin:7px 0}}</style></head><body><p><a href='/'>← Return to job queue</a></p><h1>Supervised platform pilots</h1><p>Only record a result after using a real application form. Do not enter passwords, solve CAPTCHAs, or submit an application through this page.</p><table><thead><tr><th>Platform</th><th>Current result</th><th>Notes</th><th>Record actual test</th></tr></thead><tbody>{rows}</tbody></table><section><h2>Learned form patterns</h2><p class='muted'>This is local, privacy-safe platform knowledge from your own supervised sessions. It records only field labels, control types and whether a field was recognised or needed your review. It never records answers, uploads, passwords or application submissions.</p>{knowledge_sections}</section></body></html>"""
