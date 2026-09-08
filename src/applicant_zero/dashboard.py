import html
import json
import sqlite3
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from .private_profile import load_profile
from .packets import create_application_packet
from .ai_drafting import DraftingError, create_ai_draft, load_ai_draft
from .application_session import create_session_plan
from .storage import WORKFLOW_STATUSES, initialise_database, list_board_checks, list_matches, update_workflow


def _badge(recommendation: str) -> str:
    css_class = recommendation.lower().replace(" ", "-")
    return f'<span class="badge {css_class}">{html.escape(recommendation)}</span>'


def _insights(rows: list[dict], board_checks: list[dict]) -> str:
    live_rows = [row for row in rows if row["source"].lower() != "demo"]
    relevant = [row for row in live_rows if row["recommendation"] in {"Strong apply", "Apply", "Review"}]
    available_boards = sum(board["status"] == "checked" for board in board_checks)
    workflow = {status: sum(row["workflow_status"] == status for row in live_rows) for status in WORKFLOW_STATUSES}
    workflow_summary = " · ".join(f"{status}: {count}" for status, count in workflow.items() if count)
    cards = (
        ("Live jobs collected", str(len(live_rows))),
        ("Live roles worth reviewing", str(len(relevant))),
        ("Live strong matches", str(sum(row["recommendation"] == "Strong apply" for row in live_rows))),
        ("Company boards checked", str(available_boards)),
    )
    card_html = "".join(f"<div class='insight'><strong>{html.escape(value)}</strong><span>{html.escape(label)}</span></div>" for label, value in cards)
    return f"<section class='insights'><h2>Insights</h2><div class='insight-grid'>{card_html}</div><p class='workflow-summary'>Your tracker: {html.escape(workflow_summary or 'No jobs collected yet')}</p></section>"


def build_page(database_path: Path) -> str:
    if not database_path.exists():
        rows: list[dict] = []
        board_checks: list[dict] = []
    else:
        with sqlite3.connect(database_path) as connection:
            rows = list_matches(connection)
            board_checks = list_board_checks(connection)

    source_options = sorted({row["source"] for row in rows})
    company_options = sorted({row["company"] for row in rows if row["source"].lower() != "demo"})
    table_rows = []
    for row in rows:
        reasons = "<br>".join(html.escape(reason) for reason in json.loads(row["reasons"]))
        link = html.escape(row["url"], quote=True)
        title = html.escape(row["title"])
        status_options = "".join(
            f"<option value='{html.escape(status)}'{' selected' if status == row['workflow_status'] else ''}>{html.escape(status)}</option>"
            for status in WORKFLOW_STATUSES
        )
        notes = html.escape(row["notes"], quote=True)
        job_id = html.escape(row["external_id"], quote=True)
        brief_link = "/brief?" + urlencode({"external_id": row["external_id"]})
        source = html.escape(row["source"])
        is_demo = str(row["source"]).lower() == "demo"
        table_rows.append(
            f"<tr data-status='{html.escape(row['recommendation'])}' data-source='{source}' data-company='{html.escape(row['company'], quote=True)}' data-demo='{str(is_demo).lower()}' data-search='{html.escape((row['title'] + ' ' + row['company'] + ' ' + row['location']).lower(), quote=True)}'>"
            f"<td><a href='{link}' target='_blank' rel='noreferrer'>{title}</a><small>{html.escape(row['company'])}</small><small><a href='{html.escape(brief_link, quote=True)}'>Prepare brief</a></small></td>"
            f"<td>{html.escape(row['location'])}<small>{source}</small></td>"
            f"<td>{_badge(row['recommendation'])}<small>Score: {row['score']}</small></td>"
            f"<td>{html.escape(row['resume_family'] or 'Not recommended')}</td>"
            f"<td>{reasons}</td>"
            f"<td><form method='post' action='/update'><input type='hidden' name='external_id' value='{job_id}'>"
            f"<select name='workflow_status'>{status_options}</select><input name='notes' value='{notes}' placeholder='Your note'><button type='submit'>Save</button></form></td></tr>"
        )

    body = "".join(table_rows) or "<tr><td colspan='6'>No jobs collected yet. Run a discovery source first.</td></tr>"
    insights = _insights(rows, board_checks)
    source_select = "".join(f"<option value='{html.escape(source)}'>{html.escape(source)}</option>" for source in source_options)
    company_select = "".join(f"<option value='{html.escape(company)}'>{html.escape(company)}</option>" for company in company_options)
    return f"""<!doctype html>
<html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>
<title>Applicant Zero - Review queue</title>
<style>
body{{font-family:Arial,sans-serif;background:#f5f7fb;color:#182230;margin:0}} main{{max-width:1280px;margin:0 auto;padding:32px}}
h1{{margin:0;color:#163b67}} .subtitle{{color:#5e6c84;margin:7px 0 24px}} .filters{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}} .controls{{display:flex;gap:8px;flex-wrap:wrap;margin:18px 0}} input[type=search],select{{border:1px solid #c7d2e3;border-radius:5px;padding:8px;background:#fff}} input[type=search]{{min-width:250px}}
button{{border:1px solid #c7d2e3;border-radius:5px;background:#fff;padding:8px 12px;cursor:pointer}} button.active{{background:#163b67;color:#fff}}
.insights{{margin:22px 0}} .insights h2{{font-size:18px;color:#163b67;margin:0 0 10px}} .insight-grid{{display:grid;grid-template-columns:repeat(4,minmax(130px,1fr));gap:12px}} .insight{{background:#fff;padding:14px;box-shadow:0 1px 4px #dce3ee;border-radius:4px}} .insight strong{{display:block;font-size:24px;color:#163b67}} .insight span,.workflow-summary{{color:#5e6c84;font-size:13px}} .workflow-summary{{margin:12px 0 0}}
table{{width:100%;border-collapse:collapse;background:#fff;box-shadow:0 1px 4px #dce3ee}} th{{text-align:left;background:#eaf0f8;color:#163b67;padding:12px}} td{{padding:12px;border-top:1px solid #e5eaf1;vertical-align:top;font-size:14px;line-height:1.4}} a{{color:#1261a0;font-weight:bold;text-decoration:none}} small{{display:block;color:#667085;margin-top:4px}} .badge{{display:inline-block;padding:3px 8px;border-radius:12px;font-weight:bold;font-size:12px}} .strong-apply{{background:#d9f3e6;color:#12643b}} .apply{{background:#dceeff;color:#15588a}} .review{{background:#fff1cc;color:#8a5a00}} .skip{{background:#f1f3f5;color:#596273}}
</style></head><body><main><h1>Applicant Zero</h1><p class='subtitle'>Local job review queue. Opening a link does not submit an application.</p>{insights}
<div class='filters'><button class='active' onclick="filterRows('All',this)">All</button><button onclick="filterRows('Strong apply',this)">Strong apply</button><button onclick="filterRows('Apply',this)">Apply</button><button onclick="filterRows('Review',this)">Review</button><button onclick="filterRows('Skip',this)">Skip</button></div>
<div class='controls'><input id='search' type='search' placeholder='Search role, company or location' oninput='refreshRows()'><select id='company' onchange='refreshRows()'><option value='All'>All companies</option>{company_select}</select><select id='source' onchange='refreshRows()'><option value='All'>All sources</option>{source_select}</select><button id='live-toggle' class='active' onclick='toggleLive(this)'>Live jobs only</button></div>
<table><thead><tr><th>Role</th><th>Location / source</th><th>Recommendation</th><th>Résumé</th><th>Why</th><th>Your tracker</th></tr></thead><tbody>{body}</tbody></table>
</main><script>let recommendation='All';let liveOnly=true;function filterRows(status,button){{recommendation=status;document.querySelectorAll('.filters button').forEach(b=>b.classList.remove('active'));button.classList.add('active');refreshRows()}}function toggleLive(button){{liveOnly=!liveOnly;button.classList.toggle('active',liveOnly);refreshRows()}}function refreshRows(){{const search=document.getElementById('search').value.toLowerCase();const source=document.getElementById('source').value;const company=document.getElementById('company').value;document.querySelectorAll('tbody tr').forEach(row=>{{const show=(recommendation==='All'||row.dataset.status===recommendation)&&(!liveOnly||row.dataset.demo!=='true')&&(source==='All'||row.dataset.source===source)&&(company==='All'||row.dataset.company===company)&&row.dataset.search.includes(search);row.style.display=show?'':'none'}})}}refreshRows()</script></body></html>"""


def build_brief_page(database_path: Path, external_id: str) -> str:
    with sqlite3.connect(database_path) as connection:
        rows = [row for row in list_matches(connection) if row["external_id"] == external_id]
    if not rows:
        return "<h1>Job not found</h1><p><a href='/'>Return to Applicant Zero</a></p>"
    row = rows[0]
    profile = load_profile(database_path.parent.parent / "private" / "candidate_profile.json")
    reasons = "".join(f"<li>{html.escape(reason)}</li>" for reason in json.loads(row["reasons"]))
    evidence = json.loads(row["matched_evidence"])
    missing = json.loads(row["missing_requirements"])
    description = html.escape(row["description"] or "Run the discovery command again to import this job's current description.")
    original_url = html.escape(row["url"], quote=True)
    resume_path = profile.get("resumes", {}).get(row["resume_family"], "")
    availability = profile.get("availability", {}).get("full_time_from", "")
    profile_details = ""
    if resume_path:
        profile_details = (
            f"<p>Approved résumé file: <code>{html.escape(resume_path)}</code></p>"
            f"<p>Confirmed full-time availability: <strong>{html.escape(availability)}</strong></p>"
        )
    saved_draft = load_ai_draft(database_path, external_id)
    draft_section = ""
    if saved_draft:
        draft = saved_draft.get("draft", {})
        bullets = "".join(f"<li>{html.escape(str(item))}</li>" for item in draft.get("resume_bullet_suggestions", [])) or "<li>No bullet suggestions returned.</li>"
        unsupported = "".join(f"<li>{html.escape(str(item))}</li>" for item in draft.get("unsupported_requirements", [])) or "<li>No unsupported requirements identified.</li>"
        questions = "".join(f"<li>{html.escape(str(item))}</li>" for item in draft.get("questions_to_confirm", [])) or "<li>No additional questions returned.</li>"
        answers = draft.get("application_answer_drafts", {})
        answer_rows = "".join(f"<p><strong>{html.escape(str(label).replace('_', ' ').title())}:</strong> {html.escape(str(answer))}</p>" for label, answer in answers.items()) or "<p>No application-answer drafts returned.</p>"
        draft_section = f"""<section class='card'><h2>Saved AI tailoring review</h2><p><strong>Résumé summary:</strong> {html.escape(str(draft.get('resume_summary', 'Not provided.')))}</p><h3>Suggested résumé bullets</h3><ul>{bullets}</ul><h3>Cover-letter draft</h3><pre>{html.escape(str(draft.get('cover_letter', 'Not provided.')))}</pre><h3>Common application-answer drafts</h3>{answer_rows}<h3>Unsupported requirements</h3><ul>{unsupported}</ul><h3>Questions to confirm</h3><ul>{questions}</ul><p>Review every statement against your real experience before using it.</p></section>"""
    return f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>
<title>Applicant Zero - Preparation brief</title><style>
body{{font-family:Arial,sans-serif;background:#f5f7fb;color:#182230;margin:0}} main{{max-width:900px;margin:0 auto;padding:32px}} h1,h2{{color:#163b67}} .card{{background:#fff;padding:20px;margin:16px 0;box-shadow:0 1px 4px #dce3ee}} a{{color:#1261a0;font-weight:bold}} pre{{white-space:pre-wrap;font-family:Arial,sans-serif;line-height:1.5}}</style></head>
<body><main><p><a href='/'>← Return to job queue</a></p><h1>{html.escape(row['title'])}</h1><p>{html.escape(row['company'])} · {html.escape(row['location'])} · <a href='{original_url}' target='_blank' rel='noreferrer'>Open original listing</a></p>
<section class='card'><h2>Recommended application route</h2><p>Use the <strong>{html.escape(row['resume_family'] or 'not recommended')}</strong> résumé family. Current tracker status: <strong>{html.escape(row['workflow_status'])}</strong>.</p>{profile_details}<ul>{reasons}</ul></section>
<section class='card'><h2>Evidence you can use</h2><p>{html.escape(', '.join(evidence) or 'No direct skill match was identified; read the original listing carefully.')}</p><h2>Requirements to check</h2><p>{html.escape(', '.join(missing) or 'No additional named requirement was detected by the initial matcher.')}</p></section>
<section class='card'><h2>Before applying</h2><ol><li>Read the original listing and confirm eligibility, location and seniority.</li><li>Tailor only truthful résumé wording to the role’s real requirements.</li><li>Prepare a short, specific response for any application questions.</li><li>Set the tracker to Applied only after the employer’s site confirms submission.</li></ol><form method='post' action='/packet'><input type='hidden' name='external_id' value='{html.escape(external_id, quote=True)}'><button type='submit'>Save private application packet</button></form><form method='post' action='/session-plan'><input type='hidden' name='external_id' value='{html.escape(external_id, quote=True)}'><button type='submit'>Create browser assistance plan</button></form><p>After the private evidence library and OpenAI API key are set up, you can also generate a truthful AI review draft.</p><form method='post' action='/ai-draft'><input type='hidden' name='external_id' value='{html.escape(external_id, quote=True)}'><button type='submit'>Generate AI tailoring draft</button></form></section>
{draft_section}<section class='card'><h2>Imported job description</h2><pre>{description}</pre></section></main></body></html>"""


def serve(database_path: Path, port: int = 8765) -> None:
    # Existing local databases pre-date the tracker fields. Initialise first so
    # opening the dashboard upgrades them before the first page is rendered.
    with initialise_database(database_path):
        pass

    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlsplit(self.path)
            if parsed.path == "/brief":
                external_id = parse_qs(parsed.query).get("external_id", [""])[0]
                content = build_brief_page(database_path, external_id).encode("utf-8")
            elif parsed.path == "/":
                content = build_page(database_path).encode("utf-8")
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        def do_POST(self):
            if self.path not in {"/update", "/packet", "/ai-draft", "/session-plan"}:
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", "0"))
            values = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
            external_id = values.get("external_id", [""])[0]
            if self.path == "/packet":
                try:
                    create_application_packet(database_path, external_id)
                except ValueError:
                    self.send_error(400)
                    return
                self.send_response(303)
                self.send_header("Location", "/brief?" + urlencode({"external_id": external_id}))
                self.end_headers()
                return
            if self.path == "/session-plan":
                try:
                    create_session_plan(database_path, external_id)
                except ValueError:
                    self.send_error(400)
                    return
                self.send_response(303)
                self.send_header("Location", "/brief?" + urlencode({"external_id": external_id}))
                self.end_headers()
                return
            if self.path == "/ai-draft":
                try:
                    create_ai_draft(database_path, external_id)
                except DraftingError as error:
                    content = f"<h1>Draft not created</h1><p>{html.escape(str(error))}</p><p><a href='/brief?{urlencode({'external_id': external_id})}'>Return to preparation brief</a></p>".encode("utf-8")
                    self.send_response(400)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                    return
                self.send_response(303)
                self.send_header("Location", "/brief?" + urlencode({"external_id": external_id}))
                self.end_headers()
                return
            workflow_status = values.get("workflow_status", [""])[0]
            notes = values.get("notes", [""])[0]
            try:
                with sqlite3.connect(database_path) as connection:
                    update_workflow(connection, external_id, workflow_status, notes)
            except ValueError:
                self.send_error(400)
                return
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()
        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", port), DashboardHandler)
    url = f"http://127.0.0.1:{port}"
    print(f"Applicant Zero dashboard is running at {url}")
    print("Keep this terminal open while reviewing jobs. Press Ctrl+C here when finished.")
    webbrowser.open(url)
    server.serve_forever()
