"""Create a private, printable review copy before changing an approved resume."""

import html
import json
import re
import sqlite3
from pathlib import Path

from .ai_drafting import load_ai_draft
from .private_profile import load_profile
from .storage import get_match


def _review_path(database_path: Path, row: dict) -> Path:
    safe_name = re.sub(r"[^a-z0-9]+", "-", f"{row['company']}-{row['title']}".lower()).strip("-")
    return database_path.parent.parent / "private" / "application_packets" / f"{safe_name}-resume-review.html"


def create_resume_review(database_path: Path, external_id: str) -> Path:
    with sqlite3.connect(database_path) as connection:
        row = get_match(connection, external_id)
    if row is None:
        raise ValueError("Job not found.")
    profile = load_profile(database_path.parent.parent / "private" / "candidate_profile.json")
    if not profile:
        raise ValueError("Private candidate profile is not ready.")
    draft_record = load_ai_draft(database_path, external_id)
    if not draft_record:
        raise ValueError("Generate the AI tailoring draft first, then create the resume review.")
    draft = draft_record.get("draft", {})
    resume_path = profile.get("resumes", {}).get(row["resume_family"], "")
    bullets = "".join(f"<li>{html.escape(str(item))}</li>" for item in draft.get("resume_bullet_suggestions", [])) or "<li>No bullet suggestions were returned.</li>"
    unsupported = "".join(f"<li>{html.escape(str(item))}</li>" for item in draft.get("unsupported_requirements", [])) or "<li>No unsupported requirements identified.</li>"
    questions = "".join(f"<li>{html.escape(str(item))}</li>" for item in draft.get("questions_to_confirm", [])) or "<li>No additional questions identified.</li>"
    evidence = ", ".join(json.loads(row["matched_evidence"])) or "Review the role description against the approved resume."
    output = f"""<!doctype html><html><head><meta charset='utf-8'><title>Resume review - {html.escape(row['title'])}</title><style>
body{{font-family:Arial,sans-serif;color:#1e293b;line-height:1.5;margin:42px auto;max-width:800px}}h1,h2{{color:#163b67}}.meta{{color:#53657d}}.card{{border:1px solid #dce3ee;border-radius:8px;padding:18px;margin:18px 0}}.note{{background:#fff8df;border-left:4px solid #d97706;padding:12px}}li{{margin:7px 0}}@media print{{body{{margin:20px}}.card{{break-inside:avoid}}}}
</style></head><body><h1>Tailored resume review</h1><p class='meta'>{html.escape(row['title'])} · {html.escape(row['company'])} · {html.escape(row['location'])}</p><section class='card'><h2>Base resume to edit</h2><p><strong>Family:</strong> {html.escape(row['resume_family'] or 'Not recommended')}</p><p><strong>Approved file:</strong> {html.escape(Path(resume_path).name) if resume_path else 'No approved resume file found'}</p><p><strong>Matched evidence:</strong> {html.escape(evidence)}</p></section><section class='card'><h2>Proposed professional summary</h2><p>{html.escape(str(draft.get('resume_summary', 'No summary was returned.')))}</p></section><section class='card'><h2>Suggested bullet wording</h2><ul>{bullets}</ul></section><section class='card'><h2>Requirements not supported by current evidence</h2><ul>{unsupported}</ul></section><section class='card'><h2>Questions to resolve before finalising</h2><ul>{questions}</ul></section><section class='note'><strong>Review rule:</strong> This is a private review copy, not a replacement PDF. Keep only wording you can verify from your real experience and do not add unsupported claims.</section></body></html>"""
    path = _review_path(database_path, row)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(output, encoding="utf-8")
    return path


def load_resume_review(database_path: Path, external_id: str) -> str | None:
    with sqlite3.connect(database_path) as connection:
        row = get_match(connection, external_id)
    if row is None:
        return None
    path = _review_path(database_path, row)
    return path.read_text(encoding="utf-8") if path.exists() else None
