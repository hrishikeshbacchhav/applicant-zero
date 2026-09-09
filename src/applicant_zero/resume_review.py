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
    resume_path = profile.get("editable_resume_masters", {}).get(row["resume_family"], "") or profile.get("resumes", {}).get(row["resume_family"], "")
    bullets = "".join(f"<li>{html.escape(str(item))}</li>" for item in draft.get("resume_bullet_suggestions", [])) or "<li>No bullet suggestions were returned.</li>"
    applications = draft.get("application_answer_drafts", {})
    answer_drafts = "".join(
        f"<article><h3>{html.escape(str(label).replace('_', ' ').title())}</h3><p>{html.escape(str(answer))}</p></article>"
        for label, answer in applications.items()
    ) or "<p>No application-answer drafts were returned.</p>"
    unsupported = "".join(f"<li>{html.escape(str(item))}</li>" for item in draft.get("unsupported_requirements", [])) or "<li>No unsupported requirements identified.</li>"
    questions = "".join(f"<li>{html.escape(str(item))}</li>" for item in draft.get("questions_to_confirm", [])) or "<li>No additional questions identified.</li>"
    evidence = ", ".join(json.loads(row["matched_evidence"])) or "Review the role description against the approved resume."
    output = f"""<!doctype html><html><head><meta charset='utf-8'><title>Resume review - {html.escape(row['title'])}</title><style>
body{{font-family:Arial,sans-serif;color:#1e293b;line-height:1.5;margin:42px auto;max-width:800px}}h1,h2,h3{{color:#163b67}}h3{{font-size:15px;margin-bottom:4px}}.meta{{color:#53657d}}.card{{border:1px solid #dce3ee;border-radius:8px;padding:18px;margin:18px 0}}.note{{background:#fff8df;border-left:4px solid #d97706;padding:12px}}.ready{{background:#ecfdf3;border-left:4px solid #137a45;padding:12px}}li{{margin:7px 0}}article{{border-top:1px solid #dce3ee;padding-top:8px;margin-top:8px}}@media print{{body{{margin:20px}}.card{{break-inside:avoid}}}}
</style></head><body><h1>Tailored résumé editing pack</h1><p class='meta'>{html.escape(row['title'])} · {html.escape(row['company'])} · {html.escape(row['location'])}</p><section class='card'><h2>Use this pack</h2><ol><li>Open the named base résumé and make only the reviewed, truthful changes below.</li><li>Read every highlighted requirement against the original listing before saving a final PDF.</li><li>Use the included cover letter and application-response drafts only after your own final check.</li></ol></section><section class='card'><h2>Base résumé</h2><p><strong>Family:</strong> {html.escape(row['resume_family'] or 'Not recommended')}</p><p><strong>Approved file:</strong> {html.escape(Path(resume_path).name) if resume_path else 'No approved resume file found'}</p><p><strong>Matched evidence:</strong> {html.escape(evidence)}</p></section><section class='card'><h2>Proposed professional summary</h2><p>{html.escape(str(draft.get('resume_summary', 'No summary was returned.')))}</p></section><section class='card'><h2>Suggested résumé bullet wording</h2><ul>{bullets}</ul></section><section class='card'><h2>Cover letter draft</h2><p>{html.escape(str(draft.get('cover_letter', 'No cover letter draft was returned.')))}</p></section><section class='card'><h2>Application-answer drafts</h2>{answer_drafts}</section><section class='card'><h2>Requirements not supported by current evidence</h2><ul>{unsupported}</ul></section><section class='card'><h2>Questions to resolve before finalising</h2><ul>{questions}</ul></section><section class='ready'><strong>Quality check before use:</strong> confirm the role title, employer, dates, tools, achievements, metrics and work-rights answers are all true. This pack never changes your approved PDF automatically.</section></body></html>"""
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
