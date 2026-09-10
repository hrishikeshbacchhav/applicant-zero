import html
import json
import sqlite3
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from .private_profile import load_profile
from .packets import create_application_packet
from .ai_drafting import DraftingError, create_ai_draft, create_question_draft, load_ai_draft, load_question_drafts
from .application_answers import CONFIRMATION_FIELDS, ensure_answer_library, save_confirmed_answer
from .application_routes import classify_application_url, inspect_application_route, supports_supervised_browser_handoff
from .application_session import create_session_plan
from .browser_assist import browser_setup_issue, start_browser_assistant
from .manual_import import import_listing
from .profile import RISHI_PROFILE
from .resume_review import create_resume_review, load_resume_review
from .resume_output import create_editable_resume_copy, editable_resume_copy_path
from .application_readiness import evaluate_application_readiness
from .daily_digest import create_daily_digest
from .system_health import health_page
from .reporting import outcome_summary, tracker_csv
from .platform_pilots import build_platform_pilots_page
from .discovery_registry import discovery_overview, employer_coverage_rows
from .material_manifest import create_material_manifest, material_manifest_path
from .session_trace import load_trace
from .resume_evidence import ResumeEvidenceError, create_resume_evidence_inventory, inventory_path
from .preparation_bundle import create_preparation_bundle
from .operations import operational_queue, prepare_eligible_roles
from .storage import (
    WORKFLOW_STATUSES,
    get_application_route,
    get_followup,
    get_material_review,
    get_match,
    get_submission_proof,
    initialise_database,
    latest_refresh_run,
    list_application_events,
    list_board_checks,
    list_followups,
    list_matches,
    log_application_event,
    save_application_route,
    save_material_review,
    save_submission_proof,
    complete_followup,
    complete_manual_action,
    list_manual_actions,
    save_platform_pilot,
    update_workflow,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _badge(recommendation: str) -> str:
    css_class = recommendation.lower().replace(" ", "-")
    return f'<span class="badge {css_class}">{html.escape(recommendation)}</span>'


def _insights(rows: list[dict], board_checks: list[dict], refresh_run: dict | None, followups: list[dict]) -> str:
    live_rows = [row for row in rows if row["source"].lower() != "demo"]
    current_rows = [row for row in live_rows if row["is_active"]]
    relevant = [row for row in current_rows if row["recommendation"] in {"Strong apply", "Apply", "Review"}]
    available_boards = sum(board["status"] == "checked" for board in board_checks)
    # The main dashboard is an action queue.  Keep hard-skipped discovery
    # records available under the separate filter, but do not let them inflate
    # application and weekly-priority counters.
    workflow = {status: sum(row["workflow_status"] == status for row in relevant) for status in WORKFLOW_STATUSES}
    workflow_summary = " · ".join(f"{status}: {count}" for status, count in workflow.items() if count)
    recent_cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    new_this_week = sum(row["first_seen_at"] >= recent_cutoff for row in relevant)
    cards = (
        ("Current relevant listings", str(len(relevant))),
        ("Worth reviewing", str(len(relevant))),
        ("Strong matches", str(sum(row["recommendation"] == "Strong apply" for row in current_rows))),
        ("Applications submitted", str(sum(row["workflow_status"] == "Applied" for row in live_rows))),
        ("Interviews", str(sum(row["workflow_status"] == "Interview" for row in live_rows))),
        ("Follow-ups due", str(sum(item["due_date"] <= datetime.now().date().isoformat() for item in followups))),
        ("Company boards checked", str(available_boards)),
        ("New this week", str(new_this_week)),
    )
    card_html = "".join(f"<div class='insight'><strong>{html.escape(value)}</strong><span>{html.escape(label)}</span></div>" for label, value in cards)
    refresh_summary = "No completed discovery refresh recorded yet."
    if refresh_run:
        refresh_summary = f"Last discovery refresh: {refresh_run['completed_at']} · {refresh_run['source']} · {refresh_run['collected_count']} roles collected · {refresh_run['relevant_count']} worth reviewing"
        if refresh_run.get("detail"):
            refresh_summary += f" · {refresh_run['detail']}"
        if refresh_run["unavailable_count"]:
            refresh_summary += f" · {refresh_run['unavailable_count']} source(s) unavailable"
    return f"<section class='insights'><h2>Insights</h2><div class='insight-grid'>{card_html}</div><p class='workflow-summary'>{html.escape(refresh_summary)}</p><p class='workflow-summary'>Your tracker: {html.escape(workflow_summary or 'No jobs collected yet')}</p></section>"


def _focus_panel(rows: list[dict], followups: list[dict]) -> str:
    """Show the few actions that deserve attention before the full job table."""
    current_rows = [row for row in rows if row["is_active"] and row["source"].lower() != "demo"]
    priority_rows = [row for row in current_rows if row["recommendation"] in {"Strong apply", "Apply", "Review"}]
    priority_rows.sort(key=lambda row: (-row["score"], row["first_seen_at"]), reverse=False)
    due = [item for item in followups if item["due_date"] <= datetime.now().date().isoformat() and item["status"] != "Completed"]
    actions: list[str] = []
    if priority_rows:
        top_roles = priority_rows[:3]
        links = " · ".join(
            f"<a href='/brief?{urlencode({'external_id': row['external_id']})}'>{html.escape(row['title'])}</a>"
            for row in top_roles
        )
        actions.append(f"<li><strong>Review your best current roles:</strong> {links}</li>")
    if due:
        actions.append(f"<li><strong>Follow-ups due:</strong> {len(due)} application{'s' if len(due) != 1 else ''} need a personal check-in.</li>")
    if not current_rows:
        actions.append("<li><strong>Refresh discovery:</strong> no current live listings are saved yet.</li>")
    if not actions:
        actions.append("<li>Your queue is clear. Use the filters below to review past listings or import a role you find elsewhere.</li>")
    return f"<section class='focus-panel'><div><p class='eyebrow'>Focus for today</p><h2>Start with the actions most likely to move your search forward.</h2></div><ul>{''.join(actions)}</ul></section>"


def build_page(database_path: Path) -> str:
    if not database_path.exists():
        rows: list[dict] = []
        board_checks: list[dict] = []
        refresh_run: dict | None = None
        followups: list[dict] = []
    else:
        with sqlite3.connect(database_path) as connection:
            rows = list_matches(connection)
            board_checks = list_board_checks(connection)
            refresh_run = latest_refresh_run(connection)
            followups = list_followups(connection)

    source_options = sorted({row["source"] for row in rows})
    company_options = sorted({row["company"] for row in rows if row["source"].lower() != "demo"})
    lane_options = sorted({row.get("lane") for row in rows if row.get("lane")})
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
        is_active = bool(row["is_active"])
        listing_state = "" if is_active else "<span class='listing-closed'>Listing no longer active</span>"
        duplicate_note = ""
        if row.get("duplicate_count", 1) > 1:
            duplicate_note = f"<small>{row['duplicate_count']} repeated copies combined</small>"
        last_seen = html.escape(str(row["last_seen_at"]).split(" ")[0])
        route = classify_application_url(row["url"])
        route_labels = {"assisted": "Assist ready", "pilot": "Pilot", "login_required": "Login needed", "complex": "Complex", "manual_review": "Manual review"}
        route_label = html.escape(route_labels.get(route.support_level, route.support_level))
        recent_cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        is_new = str(row["first_seen_at"]) >= recent_cutoff
        table_rows.append(
            f"<tr class='job-row' data-status='{html.escape(row['recommendation'])}' data-workflow='{html.escape(row['workflow_status'])}' data-source='{source}' data-company='{html.escape(row['company'], quote=True)}' data-lane='{html.escape(row.get('lane') or '', quote=True)}' data-demo='{str(is_demo).lower()}' data-active='{str(is_active).lower()}' data-new='{str(is_new).lower()}' data-search='{html.escape((row['title'] + ' ' + row['company'] + ' ' + row['location']).lower(), quote=True)}'>"
            f"<td><a href='{link}' target='_blank' rel='noreferrer'>{title}</a>{listing_state}<small>{html.escape(row['company'])}</small><small><a href='{html.escape(brief_link, quote=True)}'>Prepare application</a></small></td>"
            f"<td>{html.escape(row['location'])}<small>{source} · Last seen {last_seen}</small><span class='route route-{html.escape(route.support_level)}'>{html.escape(route.platform)} · {route_label}</span>{duplicate_note}</td>"
            f"<td>{_badge(row['recommendation'])}<small>Score: {row['score']}</small></td>"
            f"<td>{html.escape(row['resume_family'] or 'Not recommended')}</td>"
            f"<td>{reasons}</td>"
            f"<td><form method='post' action='/update'><input type='hidden' name='external_id' value='{job_id}'>"
            f"<select name='workflow_status'>{status_options}</select><input name='notes' value='{notes}' placeholder='Your note'><button type='submit'>Save</button></form></td></tr>"
        )

    body = "".join(table_rows) or "<tr><td colspan='6'>No jobs collected yet. Run a discovery source first.</td></tr>"
    insights = _insights(rows, board_checks, refresh_run, followups)
    focus_panel = _focus_panel(rows, followups)
    source_select = "".join(f"<option value='{html.escape(source)}'>{html.escape(source)}</option>" for source in source_options)
    company_select = "".join(f"<option value='{html.escape(company)}'>{html.escape(company)}</option>" for company in company_options)
    lane_select = "".join(f"<option value='{html.escape(lane)}'>{html.escape(lane.replace('_', ' ').title())}</option>" for lane in lane_options)
    return f"""<!doctype html>
<html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>
<title>Applicant Zero - Review queue</title>
<style>
:root{{--navy:#123154;--blue:#1468b3;--border:#dbe5f1;--muted:#64748b;--surface:#fff;--canvas:#f4f7fb}}*{{box-sizing:border-box}}body{{font-family:Inter,Segoe UI,Arial,sans-serif;background:var(--canvas);color:#1e293b;margin:0;display:grid;grid-template-columns:244px minmax(0,1fr);min-height:100vh}}main{{max-width:1540px;width:100%;margin:0 auto;padding:36px 40px}}.sidebar{{background:#102b4a;color:#d9e8fa;padding:28px 18px;display:flex;flex-direction:column;gap:28px}}.brand{{font-size:21px;font-weight:800;color:#fff;letter-spacing:-.4px}}.brand span{{display:block;margin-top:5px;font-size:12px;font-weight:600;color:#9fc1e6;letter-spacing:.04em;text-transform:uppercase}}.sidebar nav{{display:grid;gap:5px}}.sidebar nav a{{color:#c9dbef;font-size:14px;font-weight:650;padding:10px 12px;border-radius:8px}}.sidebar nav a:hover,.sidebar nav a.active{{color:#fff;background:#1a4a7d;text-decoration:none}}.sidebar .privacy{{margin-top:auto;font-size:12px;line-height:1.55;color:#a8c2df;border-top:1px solid #335778;padding:17px 10px 0}}
h1{{margin:0;color:var(--navy);letter-spacing:-.6px;font-size:30px}}.page-header{{display:flex;gap:18px;align-items:start;justify-content:space-between}}.header-kicker{{font-size:12px;color:var(--blue);font-weight:800;letter-spacing:.08em;text-transform:uppercase;margin:0 0 5px}}.subtitle{{color:#5e6c84;margin:7px 0 24px;line-height:1.55;max-width:760px}}.subtitle a{{display:inline-block;margin:2px 8px 2px 0}}.filters,.controls{{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}}input[type=search],input[name=notes],select{{border:1px solid #c7d2e3;border-radius:8px;padding:9px;background:#fff}}input[type=search]{{min-width:270px;flex:1;max-width:420px}}
button{{border:1px solid #c7d2e3;border-radius:6px;background:#fff;padding:9px 13px;cursor:pointer}} button:hover{{border-color:#7f98b9}} button.active{{background:var(--navy);color:#fff;border-color:var(--navy)}}
.import-card{{background:#fff;border:1px solid var(--border);border-radius:8px;padding:14px 18px;margin:18px 0;box-shadow:0 1px 4px var(--border)}}.import-card summary{{font-weight:bold;color:var(--navy);cursor:pointer}}.import-card p{{color:var(--muted);font-size:14px}}.import-form{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;max-width:900px}}.import-form label{{font-size:13px;font-weight:bold;color:var(--navy)}}.import-form input,.import-form textarea{{display:block;width:100%;margin-top:4px;border:1px solid #c7d2e3;border-radius:6px;padding:9px;font:inherit}}.import-form .description{{grid-column:1 / -1}}.import-form textarea{{min-height:110px;resize:vertical}}.import-form button{{width:max-content}}
.insights{{margin:22px 0}}.insights h2{{font-size:16px;color:var(--navy);margin:0 0 10px}}.insight-grid{{display:grid;grid-template-columns:repeat(6,minmax(130px,1fr));gap:12px}}.insight{{background:#fff;padding:16px;border:1px solid var(--border);box-shadow:0 4px 16px rgba(15,48,82,.04);border-radius:10px}}.insight strong{{display:block;font-size:26px;color:var(--navy)}}.insight span,.workflow-summary{{color:#5e6c84;font-size:13px}}.workflow-summary{{margin:12px 0 0}}
.focus-panel{{display:grid;grid-template-columns:minmax(260px,.8fr) minmax(0,1.2fr);gap:22px;align-items:start;background:linear-gradient(135deg,#163b67,#1c4d85);color:#fff;border-radius:12px;padding:22px 24px;margin:22px 0;box-shadow:0 4px 14px #ced8e6}}.focus-panel h2{{font-size:19px;line-height:1.35;margin:0}}.focus-panel .eyebrow{{font-size:12px;font-weight:bold;text-transform:uppercase;letter-spacing:.09em;margin:0 0 8px;color:#bcd6f4}}.focus-panel ul{{padding-left:20px;margin:4px 0;line-height:1.55}}.focus-panel li{{margin:7px 0}}.focus-panel a{{color:#fff;text-decoration:underline;text-underline-offset:3px}}
.table-wrap{{overflow-x:auto;background:#fff;border-radius:8px;box-shadow:0 1px 4px var(--border)}}table{{width:100%;border-collapse:collapse;min-width:1100px}} th{{text-align:left;background:#eaf0f8;color:var(--navy);padding:12px}} td{{padding:12px;border-top:1px solid #e5eaf1;vertical-align:top;font-size:14px;line-height:1.4}} a{{color:var(--blue);font-weight:bold;text-decoration:none}} small{{display:block;color:var(--muted);margin-top:4px}} form{{display:flex;gap:6px;flex-wrap:wrap;align-items:center}} form input[name=notes]{{min-width:170px;flex:1}} .badge,.listing-closed,.route{{display:inline-block;padding:3px 8px;border-radius:12px;font-weight:bold;font-size:12px}} .listing-closed{{display:block;width:max-content;background:#f1f3f5;color:#596273;margin-top:5px}} .route{{margin-top:6px;background:#eef4ff;color:#344c72}} .route-assisted{{background:#d9f3e6;color:#12643b}} .route-login_required,.route-complex{{background:#fff1cc;color:#8a5a00}} .strong-apply{{background:#d9f3e6;color:#12643b}} .apply{{background:#dceeff;color:#15588a}} .review{{background:#fff1cc;color:#8a5a00}} .skip{{background:#f1f3f5;color:#596273}} #no-results{{display:none;background:#fff;padding:28px;text-align:center;color:var(--muted);border-radius:8px}}
@media(max-width:1080px){{body{{grid-template-columns:1fr}}.sidebar{{display:none}}main{{padding:26px}}.insight-grid{{grid-template-columns:repeat(3,1fr)}}.focus-panel{{grid-template-columns:1fr}}}}@media(max-width:520px){{main{{padding:18px 14px}}.insight-grid{{grid-template-columns:1fr 1fr;gap:8px}}.insight{{padding:12px}}.focus-panel{{padding:18px}}.import-form{{grid-template-columns:1fr}}h1{{font-size:26px}}}}
</style></head><body><aside class='sidebar'><div><div class='brand'>Applicant Zero<span>Job search workspace</span></div><nav><a class='active' href='/'>Review queue</a><a href='/operations'>Application operations</a><a href='/discovery'>Discovery coverage</a><a href='/actions'>Manual actions</a><a href='/answers'>Application answers</a><a href='/daily-digest'>Daily priorities</a><a href='/outcomes'>Search progress</a><a href='/platform-pilots'>Platform pilots</a><a href='/health'>System health</a></nav></div><p class='privacy'>Your candidate profile, answers, resumes, activity and browser traces stay in the private local runtime.</p></aside><main><header class='page-header'><div><p class='header-kicker'>Sydney job search</p><h1>Review queue</h1><p class='subtitle'>A focused local workspace for discovery, evidence, tailored material and supervised applications. Opening a listing never submits an application.</p></div></header>{insights}
{focus_panel}
<details class='import-card'><summary>Add a job from another website</summary><p>For a role you find on SEEK, LinkedIn, Indeed or a company site, paste its public link and description here. Applicant Zero scores and prepares it locally; it does not scrape, contact or submit to that website.</p><form method='post' action='/import' class='import-form'><label>Role<input name='title' required placeholder='e.g. Data Analyst'></label><label>Company<input name='company' required></label><label>Location<input name='location' value='Sydney, NSW'></label><label>Job listing link<input name='url' type='url' required placeholder='https://...'></label><label class='description'>Job description<textarea name='description' required placeholder='Paste the responsibilities and requirements from the listing'></textarea></label><button class='active' type='submit'>Import and assess role</button></form></details>
<div class='filters'><button class='active' onclick="filterRows('All',this)">All relevant</button><button onclick="filterRows('Strong apply',this)">Strong apply</button><button onclick="filterRows('Apply',this)">Apply</button><button onclick="filterRows('Review',this)">Review</button><button onclick="filterRows('Skip',this)">Skipped</button></div>
<div class='controls'><input id='search' type='search' placeholder='Search role, company or location' oninput='refreshRows()'><select id='company' onchange='refreshRows()'><option value='All'>All companies</option>{company_select}</select><select id='lane' onchange='refreshRows()'><option value='All'>All role lanes</option>{lane_select}</select><select id='source' onchange='refreshRows()'><option value='All'>All sources</option>{source_select}</select><select id='workflow' onchange='refreshRows()'><option value='All'>All tracker stages</option>{''.join(f"<option value='{status}'>{status}</option>" for status in WORKFLOW_STATUSES)}</select><button id='current-toggle' class='active' onclick='toggleCurrent(this)'>Current listings</button><button id='live-toggle' class='active' onclick='toggleLive(this)'>Live sources</button><button id='new-toggle' onclick='toggleNew(this)'>New this week</button></div>
<div class='table-wrap'><table><thead><tr><th>Role</th><th>Location / source</th><th>Recommendation</th><th>Résumé</th><th>Why</th><th>Your tracker</th></tr></thead><tbody>{body}</tbody></table></div><div id='no-results'>No listings match the selected filters.</div>
</main><script>let recommendation='All';let liveOnly=true;let currentOnly=true;let newOnly=false;function filterRows(status,button){{recommendation=status;document.querySelectorAll('.filters button').forEach(b=>b.classList.remove('active'));button.classList.add('active');refreshRows()}}function toggleLive(button){{liveOnly=!liveOnly;button.classList.toggle('active',liveOnly);refreshRows()}}function toggleCurrent(button){{currentOnly=!currentOnly;button.classList.toggle('active',currentOnly);refreshRows()}}function toggleNew(button){{newOnly=!newOnly;button.classList.toggle('active',newOnly);refreshRows()}}function refreshRows(){{const search=document.getElementById('search').value.toLowerCase();const source=document.getElementById('source').value;const company=document.getElementById('company').value;const lane=document.getElementById('lane').value;const workflow=document.getElementById('workflow').value;let visible=0;document.querySelectorAll('tbody tr.job-row').forEach(row=>{{const relevant=row.dataset.status!=='Skip';const show=(recommendation==='All'?relevant:row.dataset.status===recommendation)&&(workflow==='All'||row.dataset.workflow===workflow)&&(lane==='All'||row.dataset.lane===lane)&&(!liveOnly||row.dataset.demo!=='true')&&(!currentOnly||row.dataset.active==='true')&&(!newOnly||row.dataset.new==='true')&&(source==='All'||row.dataset.source===source)&&(company==='All'||row.dataset.company===company)&&row.dataset.search.includes(search);row.style.display=show?'':'none';if(show)visible++}});document.getElementById('no-results').style.display=visible?'none':'block'}}refreshRows()</script></body></html>"""


def build_actions_page(database_path: Path) -> str:
    with sqlite3.connect(database_path) as connection:
        actions = list_manual_actions(connection)
    rows = "".join(
        f"<article><h2>{html.escape(action['title'])}</h2><p><strong>{html.escape(action['kind'].replace('_', ' ').title())}</strong> · {html.escape(str(action.get('company') or 'Imported role'))}</p><p>{html.escape(action['detail'])}</p><form method='post' action='/complete-action'><input type='hidden' name='action_id' value='{action['id']}'><button>Mark completed</button></form></article>"
        for action in actions
    ) or "<article><h2>No manual actions</h2><p>CAPTCHA, login, verification and unfamiliar-question handoffs will appear here.</p></article>"
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>Applicant Zero - Manual actions</title><style>body{{font-family:Arial,sans-serif;background:#f5f7fb;color:#182230;margin:0}}main{{max-width:900px;margin:0 auto;padding:32px}}h1,h2{{color:#163b67}}a{{color:#1261a0;font-weight:bold}}article{{background:#fff;border-radius:8px;padding:18px;margin:14px 0;box-shadow:0 1px 4px #dce3ee}}button{{padding:9px 13px;border:1px solid #aabbd2;border-radius:6px;background:#fff;cursor:pointer}}</style></head><body><main><p><a href='/'>← Return to job queue</a></p><h1>Manual action queue</h1><p>Only the few steps that need your attention appear here.</p>{rows}</main></body></html>"""


def build_operations_page(database_path: Path, prepared_count: int = 0) -> str:
    roles = operational_queue(database_path)
    eligible = [role for role in roles if role.eligible_for_bulk_prepare]
    rows = "".join(
        f"<article><h2>{html.escape(role.title)}</h2><p>{html.escape(role.company)} · {html.escape(role.recommendation)} · score {role.score} · {html.escape(role.workflow_status)}</p><p>{html.escape(role.next_action)}</p><p class='{'ready' if role.eligible_for_bulk_prepare else 'blocked'}'>{'Ready for local preparation' if role.eligible_for_bulk_prepare else 'Evidence to check: ' + (', '.join(role.blockers) or 'role-specific fit')}</p><a href='/brief?{urlencode({'external_id': role.external_id})}'>Open preparation brief</a></article>"
        for role in roles
    ) or "<article><h2>No current roles need action.</h2><p>Run discovery or import a suitable listing.</p></article>"
    success = f"<p class='success'>{prepared_count} role{'s' if prepared_count != 1 else ''} moved to Preparing with local materials created.</p>" if prepared_count else ""
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>Applicant Zero - Application operations</title><style>body{{font-family:Arial,sans-serif;background:#f5f7fb;color:#182230;margin:0}}main{{max-width:900px;margin:0 auto;padding:32px}}h1,h2{{color:#163b67}}a{{color:#1261a0;font-weight:bold}}article,section{{background:#fff;border-radius:8px;padding:18px;margin:14px 0;box-shadow:0 1px 4px #dce3ee}}.ready,.success{{background:#d9f3e6;color:#12643b;padding:9px;border-radius:6px}}.blocked{{background:#fff1cc;color:#8a5a00;padding:9px;border-radius:6px}}button{{padding:10px 15px;border:0;border-radius:6px;background:#163b67;color:#fff;font-weight:bold;cursor:pointer}}</style></head><body><main><p><a href='/'>← Return to job queue</a></p><h1>Application operations</h1><p>This separates local preparation work from roles that need an evidence decision. Bulk preparation creates files only: no AI usage, browser activity or employer contact.</p>{success}<section><h2>Ready now</h2><p><strong>{len(eligible)}</strong> role{'s' if len(eligible) != 1 else ''} can be prepared from your confirmed local materials.</p><form method='post' action='/prepare-eligible'><button type='submit'>Prepare up to three eligible roles</button></form></section><section><h2>Prioritised queue</h2>{rows}</section></main></body></html>"""


def build_discovery_page(database_path: Path) -> str:
    """Show what Applicant Zero can refresh directly and what needs research."""
    state = database_path.parent.parent
    private_boards = state / "data" / "company_boards.json"
    board_path = private_boards if private_boards.exists() else PROJECT_ROOT / "data" / "company_boards.starter.json"
    overview = discovery_overview(
        PROJECT_ROOT / "data" / "discovery_sources.starter.json",
        PROJECT_ROOT / "data" / "target_companies.starter.json",
        board_path,
    )
    if database_path.exists():
        with sqlite3.connect(database_path) as connection:
            board_checks = list_board_checks(connection)
    else:
        board_checks = []
    employer_rows = employer_coverage_rows(PROJECT_ROOT / "data" / "target_companies.starter.json", board_path, board_checks)
    coverage_table = "".join(
        f"<tr><td>{html.escape(str(row['company']))}</td><td>{html.escape(str(row['sector']))}</td><td>P{row['priority']}</td><td><span class='{'auto' if row['ats'] else 'research'}'>{html.escape(str(row['route']))}{(' · ' + html.escape(str(row['ats']))) if row['ats'] else ''}</span></td><td><span class='{'auto' if row['health'] == 'checked' else 'research'}'>{html.escape(str(row['health']).replace('_', ' ').title())}</span></td></tr>"
        for row in employer_rows
    )
    automated = "".join(f"<li>{html.escape(item)}</li>" for item in overview["automated_sources"])
    manual = "".join(f"<li>{html.escape(item)}</li>" for item in overview["manual_sources"])
    covered = " · ".join(html.escape(item) for item in overview["configured"]) or "None yet"
    waiting = " · ".join(html.escape(item) for item in overview["research_needed"][:20])
    more = max(0, len(overview["research_needed"]) - 20)
    if more:
        waiting += f" · and {more} more"
    return f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Applicant Zero - Discovery coverage</title><style>:root{{--navy:#163b67;--border:#dce3ee;--muted:#667085}}*{{box-sizing:border-box}}body{{font-family:Arial,sans-serif;background:#f5f7fb;color:#182230;margin:0}}main{{max-width:1100px;margin:0 auto;padding:36px 24px}}h1,h2{{color:var(--navy)}}a{{color:#1261a0;font-weight:bold}}.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:20px 0}}article,section{{background:#fff;border-radius:10px;padding:18px;box-shadow:0 1px 4px var(--border)}}article strong{{font-size:28px;color:var(--navy);display:block}}article span,.muted{{color:var(--muted)}}li{{margin:7px 0}}.table-wrap{{overflow:auto}}table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;padding:10px;border-top:1px solid var(--border)}}th{{color:var(--navy);background:#eef4fb}}.auto,.research{{display:inline-block;padding:3px 8px;border-radius:12px;font-size:12px;font-weight:bold}}.auto{{background:#d9f3e6;color:#12643b}}.research{{background:#fff1cc;color:#8a5a00}}@media(max-width:650px){{.cards{{grid-template-columns:1fr}}}}</style></head><body><main><p><a href='/'>← Return to job queue</a></p><h1>Discovery coverage</h1><p class='muted'>This is the operating map for your job search. A company is only added to automatic refresh after its public ATS board has been verified.</p><div class='cards'><article><strong>{overview['target_count']}</strong><span>target employers tracked</span></article><article><strong>{overview['configured_count']}</strong><span>verified public career boards</span></article><article><strong>{overview['source_count']}</strong><span>source routes recorded</span></article></div><section><h2>Automatic refresh</h2><ul>{automated}</ul><p><strong>Current verified boards:</strong> {covered}</p></section><section><h2>Candidate-assisted routes</h2><ul>{manual}</ul><p>Use “Add a job from another website” when you find a suitable SEEK, LinkedIn or other listing. The same scoring, tailoring and tracking workflow then applies.</p></section><section><h2>Employer-board research queue</h2><p>{waiting or 'All current targets are covered.'}</p><p class='muted'>Research queue means a target has been prioritised but no public, reliable board token has been recorded yet. It does not mean there is a vacancy.</p></section><section><h2>Employer coverage map</h2><p class='muted'>Priority 1 employers are the first research group. Public ATS refresh means the board is configured; it does not promise a current vacancy. Latest check shows the result of the most recent local refresh.</p><div class='table-wrap'><table><thead><tr><th>Employer</th><th>Sector</th><th>Priority</th><th>Discovery route</th><th>Latest check</th></tr></thead><tbody>{coverage_table}</tbody></table></div></section></main></body></html>"""


def build_answers_page(database_path: Path) -> str:
    project_root = database_path.parent.parent
    profile = load_profile(project_root / "private" / "candidate_profile.json")
    if not profile:
        return "<h1>Candidate profile is not ready</h1><p><a href='/'>Return to Applicant Zero</a></p>"
    library = ensure_answer_library(project_root, profile)
    verified = library.get("verified_answers", {})
    editable = library.get("answers_requiring_confirmation", {})
    verified_items = "".join(
        f"<li>{html.escape(key.replace('_', ' ').title())}: <strong>{'Loaded' if value else 'Missing'}</strong></li>"
        for key, value in verified.items()
    )
    fields = "".join(
        f"<form method='post' action='/answers'><label>{html.escape(label)}<input name='value' value='{html.escape(str(editable.get(key, '')), quote=True)}' placeholder='Leave blank until confirmed'></label>"
        f"<input type='hidden' name='key' value='{html.escape(key, quote=True)}'><button type='submit'>Save</button></form>"
        for key, label in CONFIRMATION_FIELDS.items()
    )
    inventory = inventory_path(project_root)
    inventory_status = "<p class='ready'>Private résumé evidence inventory is ready. AI tailoring can use exact source wording from the matching approved PDF.</p>" if inventory.exists() else "<p class='help'>Create a private evidence inventory from your approved PDFs. It reads the files locally and never changes them.</p>"
    inventory_action = "<form method='post' action='/resume-inventory'><button type='submit'>Refresh résumé evidence inventory</button></form>"
    return f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Applicant Zero - Application answers</title><style>
*{{box-sizing:border-box}}body{{font-family:Arial,sans-serif;background:#f5f7fb;color:#182230;margin:0}}main{{max-width:800px;margin:0 auto;padding:32px}}h1,h2{{color:#163b67}}.card{{background:#fff;padding:20px;margin:16px 0;border-radius:8px;box-shadow:0 1px 4px #dce3ee}}a{{color:#1261a0;font-weight:bold}}form{{display:grid;grid-template-columns:1fr auto;gap:8px;align-items:end;margin:14px 0}}label{{font-weight:bold}}input{{display:block;width:100%;margin-top:5px;padding:10px;border:1px solid #c7d2e3;border-radius:6px}}button{{padding:10px 16px;border:0;border-radius:6px;background:#163b67;color:#fff;cursor:pointer}}li{{margin:7px 0}}.help{{color:#667085}}.ready{{color:#12643b}}</style></head><body><main><p><a href='/'>← Return to job queue</a></p><h1>Reusable application answers</h1><p class='help'>These values stay in your private folder. Empty answers will never be guessed or filled automatically.</p><section class='card'><h2>Verified from your candidate profile</h2><ul>{verified_items}</ul></section><section class='card'><h2>Approved résumé evidence</h2>{inventory_status}{inventory_action}</section><section class='card'><h2>Confirm once, reuse later</h2>{fields}</section></main></body></html>"""


def build_resume_copy_page(database_path: Path, external_id: str) -> str:
    path = editable_resume_copy_path(database_path, external_id)
    if not path:
        return "<h1>Editable role copy not found</h1><p><a href='/'>Return to Applicant Zero</a></p>"
    query = urlencode({"external_id": external_id})
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>Editable role copy ready</title><style>body{{font-family:Arial,sans-serif;max-width:760px;margin:48px auto;padding:0 20px;background:#f5f7fb;color:#182230}}h1{{color:#163b67}}section{{background:#fff;padding:22px;border-radius:8px;box-shadow:0 1px 4px #dce3ee}}a.button{{display:inline-block;background:#163b67;color:#fff;padding:11px 16px;border-radius:6px;text-decoration:none;font-weight:bold}}code{{word-break:break-all}}</style></head><body><p><a href='/brief?{query}'>← Return to preparation brief</a></p><h1>Editable role copy ready</h1><section><p>Your private Word copy has been created. Edit this copy for the role; your master résumé remains unchanged.</p><p><strong>File:</strong> {html.escape(path.name)}</p><p><a class='button' href='/download-resume-copy?{query}'>Open or download Word copy</a></p><p><small>Private location: <code>{html.escape(str(path))}</code></small></p></section></body></html>"""


def build_outcomes_page(database_path: Path) -> str:
    summary = outcome_summary(database_path)
    cards = (
        ("Applications submitted", str(summary["submitted"])),
        ("Interviews", str(summary["interviews"])),
        ("Interview rate", f"{summary['interview_rate']:.1f}%"),
        ("Follow-ups due", str(summary["due_followups"])),
        ("In progress", str(summary["in_progress"])),
    )
    card_html = "".join(f"<article><strong>{html.escape(value)}</strong><span>{html.escape(label)}</span></article>" for label, value in cards)
    next_step = "Prepare your strongest current role." if summary["in_progress"] else "Review the current queue and prepare one suitable role."
    if summary["due_followups"]:
        next_step = "Complete the due follow-up before preparing another application."
    return f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Applicant Zero - Search progress</title><style>:root{{--navy:#163b67;--border:#dce3ee;--muted:#667085}}*{{box-sizing:border-box}}body{{font-family:Arial,sans-serif;background:#f5f7fb;color:#182230;margin:0}}main{{max-width:960px;margin:0 auto;padding:36px 24px}}h1,h2{{color:var(--navy)}}a{{color:#1261a0;font-weight:bold}}.cards{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:20px 0}}article,section{{background:#fff;border-radius:10px;padding:18px;box-shadow:0 1px 4px var(--border)}}article strong{{font-size:26px;color:var(--navy);display:block}}article span{{font-size:13px;color:var(--muted)}}section{{margin-top:18px;line-height:1.55}}.next{{background:#d9f3e6;color:#12643b}}@media(max-width:760px){{.cards{{grid-template-columns:repeat(2,1fr)}}}}@media(max-width:420px){{.cards{{grid-template-columns:1fr}}}}</style></head><body><main><p><a href='/'>← Return to job queue</a></p><h1>Search progress</h1><p>Private, local progress figures based only on roles you have recorded in Applicant Zero.</p><div class='cards'>{card_html}</div><section class='next'><h2>Next action</h2><p>{html.escape(next_step)}</p></section><section><h2>How to use these figures</h2><p>“Applications submitted” includes roles marked Applied, Interview or Closed. The interview rate is interviews divided by submitted applications. These figures do not infer employer responses and never send follow-ups automatically.</p><p><a href='/export-tracker'>Download the full tracker CSV</a> when you want to review details in Excel.</p></section></main></body></html>"""


def build_brief_page(database_path: Path, external_id: str) -> str:
    with sqlite3.connect(database_path) as connection:
        row = get_match(connection, external_id)
        saved_route = get_application_route(connection, external_id)
        events = list_application_events(connection, external_id)
        material_review = get_material_review(connection, external_id)
        submission_proof = get_submission_proof(connection, external_id)
        followup = get_followup(connection, external_id)
    if row is None:
        return "<h1>Job not found</h1><p><a href='/'>Return to Applicant Zero</a></p>"
    profile = load_profile(database_path.parent.parent / "private" / "candidate_profile.json")
    answer_library = ensure_answer_library(database_path.parent.parent, profile) if profile else {}
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
    predicted_route = classify_application_url(row["url"])
    route = saved_route or {
        "platform": predicted_route.platform,
        "support_level": predicted_route.support_level,
        "apply_url": predicted_route.apply_url,
        "account_required": predicted_route.account_required,
        "captcha_detected": predicted_route.captcha_detected,
        "field_count": predicted_route.field_count,
        "required_field_count": predicted_route.required_field_count,
        "detail": predicted_route.detail,
        "checked_at": "Not scanned yet",
    }
    route_labels = {"assisted": "Browser assistance ready", "pilot": "Supervised pilot", "login_required": "Candidate login required", "complex": "Complex multi-step form", "manual_review": "Manual review required"}
    route_label = route_labels.get(route["support_level"], route["support_level"])
    route_details = (
        f"<p><strong>{html.escape(route['platform'])}:</strong> {html.escape(route_label)}</p>"
        f"<p>{html.escape(route['detail'])}</p>"
        f"<p>Account required: <strong>{'Yes' if route['account_required'] else 'No detected requirement'}</strong> · "
        f"CAPTCHA detected: <strong>{'Yes' if route['captcha_detected'] else 'No'}</strong> · "
        f"Fields detected: <strong>{route['field_count']}</strong> · Required fields detected: <strong>{route['required_field_count']}</strong></p>"
    )
    verified_count = len([value for value in answer_library.get("verified_answers", {}).values() if value])
    confirmation_count = len([value for value in answer_library.get("answers_requiring_confirmation", {}).values() if not value])
    setup_issue = browser_setup_issue()
    setup_html = f"<p class='notice'>{html.escape(setup_issue)}</p>" if setup_issue else "<p class='ready'>Browser assistance is installed and ready.</p>"
    event_items = "".join(
        f"<li><strong>{html.escape(event['status'].replace('_', ' ').title())}</strong> · {html.escape(event['created_at'])}<br>{html.escape(event['detail'])}</li>"
        for event in events
    ) or "<li>No application activity has been recorded for this role.</li>"
    browser_button = ""
    if supports_supervised_browser_handoff(predicted_route) and not setup_issue:
        button_label = "Open assisted application" if route["support_level"] in {"assisted", "pilot"} else "Open supervised login handoff"
        browser_button = f"<form method='post' action='/assist'><input type='hidden' name='external_id' value='{html.escape(external_id, quote=True)}'><button class='primary' type='submit'>{button_label}</button></form>"
    saved_draft = load_ai_draft(database_path, external_id)
    session_trace = load_trace(database_path, external_id)
    trace_link = ""
    if session_trace:
        trace_link = f"<p class='help'><a href='/session-trace?{urlencode({'external_id': external_id})}'>View browser session trace</a> · {len(session_trace.get('events', []))} recorded event(s)</p>"
    question_drafts = load_question_drafts(database_path, external_id)
    resume_review_button = f"<form method='post' action='/resume-review'><input type='hidden' name='external_id' value='{html.escape(external_id, quote=True)}'><button type='submit'>Create tailored resume review</button></form>"
    resume_copy_button = f"<form method='post' action='/resume-copy'><input type='hidden' name='external_id' value='{html.escape(external_id, quote=True)}'><button type='submit'>Create editable role copy</button></form>"
    manifest_button = f"<form method='post' action='/material-manifest'><input type='hidden' name='external_id' value='{html.escape(external_id, quote=True)}'><button type='submit'>Create evidence manifest</button></form>"
    preparation_bundle_button = f"<form method='post' action='/prepare-role'><input type='hidden' name='external_id' value='{html.escape(external_id, quote=True)}'><button type='submit'>Prepare role materials</button></form><p class='muted'>Creates the local evidence manifest, preparation packet, browser plan and editable Word copy. It does not contact the employer or use AI credits.</p>"
    manifest = material_manifest_path(database_path, external_id)
    manifest_status = f"<p class='ready'>Role evidence manifest saved: <code>{html.escape(manifest.name)}</code></p>" if manifest else ""
    editable_copy = editable_resume_copy_path(database_path, external_id)
    resume_copy_status = ""
    if editable_copy:
        copy_query = urlencode({"external_id": external_id})
        resume_copy_status = f"<p class='ready'>An editable role copy is ready. <a href='/resume-copy?{copy_query}'>Open or download it</a></p>"
    draft_section = ""
    if saved_draft:
        draft = saved_draft.get("draft", {})
        usage = saved_draft.get("api_usage", {})
        usage_summary = ""
        if usage:
            usage_summary = f"<p class='help'>AI drafting usage: {html.escape(str(saved_draft.get('model', 'unknown model')))} · {html.escape(str(usage.get('input_tokens', 0)))} input tokens · {html.escape(str(usage.get('output_tokens', 0)))} output tokens.</p>"
        bullets = "".join(f"<li>{html.escape(str(item))}</li>" for item in draft.get("resume_bullet_suggestions", [])) or "<li>No bullet suggestions returned.</li>"
        unsupported = "".join(f"<li>{html.escape(str(item))}</li>" for item in draft.get("unsupported_requirements", [])) or "<li>No unsupported requirements identified.</li>"
        questions = "".join(f"<li>{html.escape(str(item))}</li>" for item in draft.get("questions_to_confirm", [])) or "<li>No additional questions returned.</li>"
        answers = draft.get("application_answer_drafts", {})
        answer_rows = "".join(f"<p><strong>{html.escape(str(label).replace('_', ' ').title())}:</strong> {html.escape(str(answer))}</p>" for label, answer in answers.items()) or "<p>No application-answer drafts returned.</p>"
        draft_section = f"""<section class='card'><h2>Saved AI tailoring review</h2>{usage_summary}<p><strong>Résumé summary:</strong> {html.escape(str(draft.get('resume_summary', 'Not provided.')))}</p><h3>Suggested résumé bullets</h3><ul>{bullets}</ul><h3>Cover-letter draft</h3><pre>{html.escape(str(draft.get('cover_letter', 'Not provided.')))}</pre><h3>Common application-answer drafts</h3>{answer_rows}<h3>Unsupported requirements</h3><ul>{unsupported}</ul><h3>Questions to confirm</h3><ul>{questions}</ul><p>Review every statement against your real experience before using it.</p></section>"""
    readiness = evaluate_application_readiness(database_path, row, bool(material_review and material_review["materials_reviewed"]))
    readiness_rows = "".join(
        f"<li class='{'complete' if item.complete else 'pending'}'><strong>{'Complete' if item.complete else 'Needed'}:</strong> {html.escape(item.label)} - {html.escape(item.detail)}</li>"
        for item in readiness
    )
    ready_to_submit = all(item.complete for item in readiness)
    readiness_status = "Ready for your final employer-site review." if ready_to_submit else "Complete the remaining items before treating this as ready to submit."
    proof_html = ""
    if submission_proof:
        followup_html = ""
        if followup:
            if followup["status"] == "Completed":
                followup_html = f"<p class='ready'>Follow-up completed: {html.escape(str(followup.get('completed_at', '')))}</p>"
            else:
                followup_html = f"<p class='notice'>Planned follow-up date: <strong>{html.escape(followup['due_date'])}</strong>. Applicant Zero will not send anything automatically.</p><form method='post' action='/complete-followup'><input type='hidden' name='external_id' value='{html.escape(external_id, quote=True)}'><input name='followup_note' placeholder='Optional follow-up note'><button type='submit'>Mark follow-up completed</button></form>"
        proof_html = f"<p class='ready'><strong>Employer confirmation recorded:</strong> {html.escape(submission_proof['submitted_at'])}</p>{followup_html}"
    else:
        proof_html = f"<form method='post' action='/submission-proof' class='stacked'><input type='hidden' name='external_id' value='{html.escape(external_id, quote=True)}'><label>Confirmation reference or email subject<input name='confirmation_reference' placeholder='Optional reference'></label><label>Confirmation-page link<input name='confirmation_url' type='url' placeholder='Optional https://... link'></label><label>Submission note<input name='submission_note' placeholder='At least one confirmation detail is required'></label><button type='submit'>Record employer confirmation and mark Applied</button></form>"
    question_items = "".join(
        f"<article class='question-draft'><p><strong>Question:</strong> {html.escape(str(item.get('question', '')))}</p><p><strong>Draft:</strong> {html.escape(str(item.get('answer', '')))}</p>"
        f"<p class='pending'>{html.escape(str(item.get('unsupported_requirement', '') or item.get('question_to_confirm', '')))}</p></article>"
        for item in question_drafts
    ) or "<p class='help'>No job-specific question drafts yet.</p>"
    return f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>
<title>Applicant Zero - Preparation brief</title><style>
*{{box-sizing:border-box}}body{{font-family:Arial,sans-serif;background:#f5f7fb;color:#182230;margin:0}} main{{max-width:900px;margin:0 auto;padding:32px}} h1,h2{{color:#163b67}} .card{{background:#fff;padding:20px;margin:16px 0;box-shadow:0 1px 4px #dce3ee;border-radius:8px}} a{{color:#1261a0;font-weight:bold}} pre{{white-space:pre-wrap;font-family:Arial,sans-serif;line-height:1.5}} form{{display:inline-block;margin:5px 6px 5px 0}}button{{border:1px solid #aabbd2;border-radius:6px;background:#fff;padding:9px 13px;cursor:pointer}}button.primary{{background:#163b67;color:#fff;border-color:#163b67}}.notice{{background:#fff1cc;color:#704b00;padding:10px;border-radius:6px}}.ready{{background:#d9f3e6;color:#12643b;padding:10px;border-radius:6px}}.pending{{color:#8a5a00}}.complete{{color:#12643b}}.help{{color:#667085;font-size:13px}}.stacked{{display:grid;grid-template-columns:1fr;gap:8px;max-width:520px}}.stacked label{{font-weight:bold;font-size:13px}}.stacked input,.stacked textarea{{display:block;width:100%;margin-top:4px;border:1px solid #c7d2e3;border-radius:6px;padding:8px;font:inherit}}.stacked textarea{{min-height:100px;resize:vertical}}.question-draft{{border-top:1px solid #dce3ee;padding:12px 0}}.question-draft p{{white-space:pre-wrap}}.activity li{{margin-bottom:10px}}</style></head>
<body><main><p><a href='/'>← Return to job queue</a></p><h1>{html.escape(row['title'])}</h1><p>{html.escape(row['company'])} · {html.escape(row['location'])} · <a href='{original_url}' target='_blank' rel='noreferrer'>Open original listing</a></p>
<section class='card'><h2>Recommended application route</h2><p>Use the <strong>{html.escape(row['resume_family'] or 'not recommended')}</strong> résumé family. Current tracker status: <strong>{html.escape(row['workflow_status'])}</strong>.</p>{profile_details}<ul>{reasons}</ul></section>
<section class='card'><h2>Evidence you can use</h2><p>{html.escape(', '.join(evidence) or 'No direct skill match was identified; read the original listing carefully.')}</p><h2>Requirements to check</h2><p>{html.escape(', '.join(missing) or 'No additional named requirement was detected by the initial matcher.')}</p></section>
<section class='card'><h2>Application compatibility</h2>{route_details}<p>Your private answer library currently has <strong>{verified_count}</strong> verified answers and <strong>{confirmation_count}</strong> unanswered items.</p>{setup_html}<form method='post' action='/route-check'><input type='hidden' name='external_id' value='{html.escape(external_id, quote=True)}'><button type='submit'>Scan application form</button></form>{browser_button}<p>The assisted browser fills contact details and the approved résumé, highlights unresolved required fields, and leaves the final submission untouched.</p>{trace_link}</section>
<section class='card'><h2>Application readiness</h2><p class='{'ready' if ready_to_submit else 'notice'}'>{html.escape(readiness_status)}</p><ol>{readiness_rows}</ol><form method='post' action='/review-materials'><input type='hidden' name='external_id' value='{html.escape(external_id, quote=True)}'><input name='review_note' placeholder='Optional review note'><button type='submit'>Mark materials reviewed</button></form></section>
<section class='card'><h2>Application question workspace</h2><p>Paste an unfamiliar role-specific application question to produce a private review draft from your verified evidence. Visa, work-rights, identity and health questions remain for you to answer directly.</p><form method='post' action='/question-draft' class='stacked'><input type='hidden' name='external_id' value='{html.escape(external_id, quote=True)}'><label>Application question<textarea name='question' required placeholder='Paste the employer question here'></textarea></label><button type='submit'>Draft truthful response</button></form>{question_items}</section>
<section class='card'><h2>Before applying</h2><ol><li>Read the original listing and confirm eligibility, location and seniority.</li><li>Tailor only truthful résumé wording to the role’s real requirements.</li><li>Prepare a short, specific response for any application questions.</li><li>Set the tracker to Applied only after the employer’s site confirms submission.</li></ol>{preparation_bundle_button}{manifest_button}{manifest_status}<form method='post' action='/packet'><input type='hidden' name='external_id' value='{html.escape(external_id, quote=True)}'><button type='submit'>Save private application packet</button></form><form method='post' action='/session-plan'><input type='hidden' name='external_id' value='{html.escape(external_id, quote=True)}'><button type='submit'>Create browser assistance plan</button></form><p>After the private evidence library and OpenAI API key are set up, you can also generate a truthful AI review draft.</p><form method='post' action='/ai-draft'><input type='hidden' name='external_id' value='{html.escape(external_id, quote=True)}'><button type='submit'>Generate AI tailoring draft</button></form>{resume_review_button}{resume_copy_button}{resume_copy_status}</section>
<section class='card'><h2>After you submit</h2><p>Applicant Zero never submits for you. After the employer site confirms your submission, save one confirmation detail here to update the tracker.</p>{proof_html}</section>
{draft_section}<section class='card'><h2>Application activity</h2><ul class='activity'>{event_items}</ul></section><section class='card'><h2>Imported job description</h2><pre>{description}</pre></section></main></body></html>"""


def build_session_trace_page(database_path: Path, external_id: str) -> str:
    """Render the candidate's private browser handoff history for one role."""
    trace = load_trace(database_path, external_id)
    query = urlencode({"external_id": external_id})
    if not trace:
        return f"<!doctype html><title>No browser trace</title><main><p><a href='/brief?{query}'>← Return to preparation brief</a></p><h1>No browser session has been recorded</h1><p>Open browser assistance for this role to start a private session trace.</p></main>"
    events = []
    for item in trace.get("events", []):
        screenshot = str(item.get("screenshot", "")).strip()
        evidence = f"<p class='muted'>Screenshot saved privately: {html.escape(Path(screenshot).name)}</p>" if screenshot else ""
        page_url = str(item.get("page_url", "")).strip()
        url = f"<p><a href='{html.escape(page_url, quote=True)}' target='_blank' rel='noreferrer'>Open recorded page</a></p>" if page_url else ""
        events.append(f"<article><strong>{html.escape(str(item.get('event', '')).replace('_', ' ').title())}</strong><span>{html.escape(str(item.get('at', '')))}</span><p>{html.escape(str(item.get('detail', '')))}</p>{url}{evidence}</article>")
    event_html = "".join(events) or "<p>No events were recorded before the browser closed.</p>"
    form_pages = []
    for page in trace.get("form_pages", []):
        fields = page.get("fields", [])
        recognised = sum(field.get("handling") == "recognised" for field in fields)
        review = len(fields) - recognised
        rows = "".join(
            f"<li><strong>{html.escape(str(field.get('control', 'field')).title())}</strong> · {html.escape(str(field.get('handling', 'candidate review')).title())} · {html.escape(str(field.get('label', '')))}</li>"
            for field in fields
        )
        form_pages.append(f"<article><strong>Form page inventory</strong><span>{html.escape(str(page.get('at', '')))}</span><p>{recognised} recognised field(s) · {review} field(s) for candidate review.</p><ul>{rows}</ul></article>")
    inventory_html = "".join(form_pages)
    return f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Applicant Zero - Browser trace</title><style>body{{font-family:Arial,sans-serif;background:#f5f7fb;color:#182230;margin:0}}main{{max-width:860px;margin:0 auto;padding:36px 24px}}a{{color:#1261a0;font-weight:bold}}h1{{color:#163b67}}article{{background:#fff;border-radius:9px;padding:16px 18px;margin:12px 0;box-shadow:0 1px 4px #dce3ee}}article strong{{color:#163b67;display:block}}article span,.muted{{font-size:13px;color:#667085}}article p{{line-height:1.5}}li{{margin:7px 0}}</style></head><body><main><p><a href='/brief?{query}'>← Return to preparation brief</a></p><h1>Browser session trace</h1><p>{html.escape(str(trace.get('job', {}).get('title', 'Application')))} · {html.escape(str(trace.get('job', {}).get('company', '')))} · {html.escape(str(trace.get('platform', '')))}</p><p class='muted'>This local trace records browser-assistance events. It does not record passwords and it never records a submitted application unless you save the employer confirmation separately.</p>{inventory_html}{event_html}</main></body></html>"""


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
            elif parsed.path == "/session-trace":
                external_id = parse_qs(parsed.query).get("external_id", [""])[0]
                content = build_session_trace_page(database_path, external_id).encode("utf-8")
            elif parsed.path == "/resume-review":
                external_id = parse_qs(parsed.query).get("external_id", [""])[0]
                review = load_resume_review(database_path, external_id)
                content = (review or "<h1>Resume review not created</h1><p><a href='/'>Return to Applicant Zero</a></p>").encode("utf-8")
            elif parsed.path == "/resume-copy":
                external_id = parse_qs(parsed.query).get("external_id", [""])[0]
                content = build_resume_copy_page(database_path, external_id).encode("utf-8")
            elif parsed.path == "/download-resume-copy":
                external_id = parse_qs(parsed.query).get("external_id", [""])[0]
                path = editable_resume_copy_path(database_path, external_id)
                if not path:
                    self.send_error(404)
                    return
                content = path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            elif parsed.path == "/answers":
                content = build_answers_page(database_path).encode("utf-8")
            elif parsed.path == "/actions":
                content = build_actions_page(database_path).encode("utf-8")
            elif parsed.path == "/operations":
                prepared_count = int(parse_qs(parsed.query).get("prepared", ["0"])[0] or "0")
                content = build_operations_page(database_path, prepared_count).encode("utf-8")
            elif parsed.path == "/discovery":
                content = build_discovery_page(database_path).encode("utf-8")
            elif parsed.path == "/outcomes":
                content = build_outcomes_page(database_path).encode("utf-8")
            elif parsed.path == "/daily-digest":
                content = create_daily_digest(database_path).read_bytes()
            elif parsed.path == "/health":
                content = health_page(database_path.parent.parent).encode("utf-8")
            elif parsed.path == "/export-tracker":
                content = tracker_csv(database_path).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", "attachment; filename=applicant-zero-tracker.csv")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            elif parsed.path == "/platform-pilots":
                content = build_platform_pilots_page(database_path).encode("utf-8")
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
            if self.path not in {"/update", "/packet", "/ai-draft", "/session-plan", "/route-check", "/assist", "/answers", "/resume-inventory", "/import", "/resume-review", "/resume-copy", "/material-manifest", "/prepare-role", "/prepare-eligible", "/review-materials", "/submission-proof", "/question-draft", "/complete-followup", "/complete-action", "/platform-pilot"}:
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", "0"))
            values = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
            external_id = values.get("external_id", [""])[0]
            if self.path == "/resume-inventory":
                try:
                    create_resume_evidence_inventory(database_path.parent.parent)
                except ResumeEvidenceError as error:
                    content = f"<h1>Résumé evidence inventory was not created</h1><p>{html.escape(str(error))}</p><p><a href='/answers'>Return to application answers</a></p>".encode("utf-8")
                    self.send_response(400)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                    return
                self.send_response(303)
                self.send_header("Location", "/answers")
                self.end_headers()
                return
            if self.path == "/material-manifest":
                try:
                    create_material_manifest(database_path, external_id)
                except ValueError:
                    self.send_error(400)
                    return
                self.send_response(303)
                self.send_header("Location", "/brief?" + urlencode({"external_id": external_id}))
                self.end_headers()
                return
            if self.path == "/prepare-role":
                try:
                    create_preparation_bundle(database_path, external_id)
                except ValueError:
                    self.send_error(400)
                    return
                self.send_response(303)
                self.send_header("Location", "/brief?" + urlencode({"external_id": external_id}))
                self.end_headers()
                return
            if self.path == "/prepare-eligible":
                prepared = prepare_eligible_roles(database_path)
                self.send_response(303)
                self.send_header("Location", "/operations?" + urlencode({"prepared": len(prepared)}))
                self.end_headers()
                return
            if self.path == "/resume-copy":
                try:
                    create_editable_resume_copy(database_path, external_id)
                except ValueError:
                    self.send_error(400)
                    return
                self.send_response(303)
                self.send_header("Location", "/resume-copy?" + urlencode({"external_id": external_id}))
                self.end_headers()
                return
            if self.path == "/platform-pilot":
                try:
                    with sqlite3.connect(database_path) as connection:
                        save_platform_pilot(connection, values.get("platform", [""])[0], values.get("status", [""])[0], values.get("note", [""])[0])
                except ValueError:
                    self.send_error(400)
                    return
                self.send_response(303)
                self.send_header("Location", "/platform-pilots")
                self.end_headers()
                return
            if self.path == "/complete-followup":
                with sqlite3.connect(database_path) as connection:
                    complete_followup(connection, external_id, values.get("followup_note", [""])[0])
                self.send_response(303)
                self.send_header("Location", "/brief?" + urlencode({"external_id": external_id}))
                self.end_headers()
                return
            if self.path == "/complete-action":
                try:
                    action_id = int(values.get("action_id", ["0"])[0])
                except ValueError:
                    self.send_error(400)
                    return
                with sqlite3.connect(database_path) as connection:
                    complete_manual_action(connection, action_id)
                self.send_response(303)
                self.send_header("Location", "/actions")
                self.end_headers()
                return
            if self.path == "/question-draft":
                try:
                    create_question_draft(database_path, external_id, values.get("question", [""])[0])
                except DraftingError as error:
                    content = f"<h1>Question draft not created</h1><p>{html.escape(str(error))}</p><p><a href='/brief?{urlencode({'external_id': external_id})}'>Return to preparation brief</a></p>".encode("utf-8")
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
            if self.path == "/review-materials":
                with sqlite3.connect(database_path) as connection:
                    save_material_review(connection, external_id, values.get("review_note", [""])[0])
                self.send_response(303)
                self.send_header("Location", "/brief?" + urlencode({"external_id": external_id}))
                self.end_headers()
                return
            if self.path == "/submission-proof":
                try:
                    with sqlite3.connect(database_path) as connection:
                        save_submission_proof(
                            connection,
                            external_id,
                            values.get("confirmation_reference", [""])[0],
                            values.get("confirmation_url", [""])[0],
                            values.get("submission_note", [""])[0],
                        )
                        update_workflow(connection, external_id, "Applied", values.get("submission_note", [""])[0])
                except ValueError as error:
                    content = f"<h1>Submission confirmation was not recorded</h1><p>{html.escape(str(error))}</p><p><a href='/brief?{urlencode({'external_id': external_id})}'>Return to preparation brief</a></p>".encode("utf-8")
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
            if self.path == "/resume-review":
                try:
                    create_resume_review(database_path, external_id)
                except ValueError as error:
                    content = f"<h1>Resume review was not created</h1><p>{html.escape(str(error))}</p><p><a href='/brief?{urlencode({'external_id': external_id})}'>Return to preparation brief</a></p>".encode("utf-8")
                    self.send_response(400)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                    return
                self.send_response(303)
                self.send_header("Location", "/resume-review?" + urlencode({"external_id": external_id}))
                self.end_headers()
                return
            if self.path == "/import":
                try:
                    with sqlite3.connect(database_path) as connection:
                        job = import_listing(
                            connection,
                            RISHI_PROFILE,
                            title=values.get("title", [""])[0],
                            company=values.get("company", [""])[0],
                            location=values.get("location", [""])[0],
                            url=values.get("url", [""])[0],
                            description=values.get("description", [""])[0],
                        )
                except ValueError as error:
                    content = f"<h1>Job was not imported</h1><p>{html.escape(str(error))}</p><p><a href='/'>Return to job queue</a></p>".encode("utf-8")
                    self.send_response(400)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                    return
                self.send_response(303)
                self.send_header("Location", "/brief?" + urlencode({"external_id": job.external_id}))
                self.end_headers()
                return
            if self.path == "/answers":
                profile = load_profile(database_path.parent.parent / "private" / "candidate_profile.json")
                try:
                    save_confirmed_answer(
                        database_path.parent.parent,
                        profile,
                        values.get("key", [""])[0],
                        values.get("value", [""])[0],
                    )
                except ValueError:
                    self.send_error(400)
                    return
                self.send_response(303)
                self.send_header("Location", "/answers")
                self.end_headers()
                return
            if self.path == "/route-check":
                with sqlite3.connect(database_path) as connection:
                    job = get_match(connection, external_id)
                if job is None:
                    self.send_error(400)
                    return
                try:
                    route = inspect_application_route(job["url"])
                    with sqlite3.connect(database_path) as connection:
                        save_application_route(connection, external_id, route)
                        log_application_event(connection, external_id, "route_check", "completed", route.detail)
                except (OSError, ValueError) as error:
                    with sqlite3.connect(database_path) as connection:
                        log_application_event(connection, external_id, "route_check", "unavailable", f"Application form could not be scanned: {error}")
                self.send_response(303)
                self.send_header("Location", "/brief?" + urlencode({"external_id": external_id}))
                self.end_headers()
                return
            if self.path == "/assist":
                started = start_browser_assistant(database_path, external_id)
                if not started:
                    with sqlite3.connect(database_path) as connection:
                        log_application_event(connection, external_id, "browser_assist", "already_running", "An assisted browser is already open for this role.")
                self.send_response(303)
                self.send_header("Location", "/brief?" + urlencode({"external_id": external_id}))
                self.end_headers()
                return
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
