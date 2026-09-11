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
from .application_routes import classify_application_url
from .manual_import import import_listing
from .profile import RISHI_PROFILE
from .resume_review import create_resume_review, load_resume_review
from .resume_output import create_editable_resume_copy, editable_resume_copy_path
from .application_readiness import evaluate_application_readiness
from .daily_digest import create_daily_digest
from .system_health import health_page
from .reporting import outcome_summary, tracker_csv
from .platform_pilots import build_platform_pilots_page
from .discovery_registry import add_public_board_url, board_health_summary, discovery_overview, employer_coverage_rows, public_board_from_url
from .discovery_registry import load_targets
from .discovery_priority import prioritise_targets
from .material_manifest import create_material_manifest, material_manifest_path
from .resume_evidence import ResumeEvidenceError, create_resume_evidence_inventory, inventory_path
from .preparation_bundle import create_preparation_bundle
from .operations import operational_queue, prepare_eligible_roles
from .discovery_health import discovery_log_status
from .campaigns import campaign_query_allocation, discovery_query_status, load_campaigns, save_enabled_campaigns
from .job_intelligence import inspect_job
from .sources.company_boards import fetch_public_board
from .gmail_sync import GmailSetupError, gmail_setup_status, sync_gmail
from .storage import (
    WORKFLOW_STATUSES,
    get_followup,
    get_material_review,
    get_match,
    get_submission_proof,
    initialise_database,
    latest_refresh_run,
    list_board_checks,
    list_board_check_trends,
    list_followups,
    list_matches,
    latest_email_sync_run,
    list_email_events,
    save_material_review,
    save_submission_proof,
    complete_followup,
    complete_manual_action,
    list_manual_actions,
    save_platform_pilot,
    update_workflow,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _workspace_navigation(active: str) -> str:
    """Render the shared workspace navigation with one clear current section."""
    links = (
        ("queue", "/", "Review queue"),
        ("campaigns", "/campaigns", "Search campaigns"),
        ("operations", "/operations", "Preparation queue"),
        ("discovery", "/discovery", "Discovery coverage"),
        ("answers", "/answers", "Application answers"),
        ("email", "/email-updates", "Email updates"),
        ("outcomes", "/outcomes", "Search progress"),
        ("health", "/health", "System health"),
        ("guide", "/guide", "How to use this"),
    )
    return "".join(
        f"<a{' class=\'active\'' if identifier == active else ''} href='{href}'>{label}</a>"
        for identifier, href, label in links
    )


def _workspace_page(active: str, kicker: str, title: str, subtitle: str, content: str) -> str:
    """Use a consistent responsive shell for the primary job-search pages."""
    return f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Applicant Zero - {html.escape(title)}</title><style>
:root{{--navy:#123154;--blue:#1468b3;--border:#dbe5f1;--muted:#64748b;--canvas:#f4f7fb;--surface:#fff}}*{{box-sizing:border-box}}body{{font-family:Inter,Segoe UI,Arial,sans-serif;background:var(--canvas);color:#1e293b;margin:0;display:grid;grid-template-columns:244px minmax(0,1fr);min-height:100vh}}main{{max-width:1380px;width:100%;margin:0 auto;padding:36px 40px}}.sidebar{{background:#102b4a;color:#d9e8fa;padding:28px 18px;display:flex;flex-direction:column;gap:28px}}.brand{{font-size:21px;font-weight:800;color:#fff;letter-spacing:-.4px}}.brand span{{display:block;margin-top:5px;font-size:12px;font-weight:600;color:#9fc1e6;letter-spacing:.04em;text-transform:uppercase}}.sidebar nav{{display:grid;gap:5px}}.sidebar nav a{{color:#c9dbef;font-size:14px;font-weight:650;padding:10px 12px;border-radius:8px;text-decoration:none}}.sidebar nav a:hover,.sidebar nav a.active{{color:#fff;background:#1a4a7d}}.privacy{{margin-top:auto;font-size:12px;line-height:1.55;color:#a8c2df;border-top:1px solid #335778;padding:17px 10px 0}}h1,h2{{color:var(--navy)}}h1{{margin:0;font-size:30px;letter-spacing:-.6px}}h2{{font-size:19px;margin:0 0 8px}}a{{color:var(--blue);font-weight:700}}.eyebrow{{font-size:12px;color:var(--blue);font-weight:800;letter-spacing:.08em;text-transform:uppercase;margin:0 0 5px}}.lead{{color:var(--muted);line-height:1.55;max-width:780px;margin:8px 0 25px}}.section-card{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px 22px;margin:16px 0;box-shadow:0 4px 16px rgba(15,48,82,.04)}}.card-grid{{display:grid;grid-template-columns:repeat(3,minmax(160px,1fr));gap:12px;margin:18px 0}}.metric{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:17px;box-shadow:0 4px 16px rgba(15,48,82,.04)}}.metric strong{{display:block;font-size:28px;color:var(--navy)}}.metric span,.muted,small{{color:var(--muted)}}.notice{{background:#eaf2fd;border-left:4px solid var(--blue);padding:13px 15px;border-radius:7px;line-height:1.5}}.success{{background:#d9f3e6;color:#12643b;padding:10px;border-radius:7px}}.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}}.grid>.section-card{{margin:0}}.table-wrap{{overflow:auto}}table{{width:100%;border-collapse:collapse;min-width:700px}}th,td{{text-align:left;padding:11px;border-top:1px solid var(--border);vertical-align:top}}th{{color:var(--navy);background:#eef4fb}}li{{margin:7px 0;line-height:1.45}}button{{background:var(--navy);color:#fff;border:0;border-radius:7px;padding:10px 14px;font-weight:700;cursor:pointer}}button:hover{{background:#1b4c80}}input,select{{border:1px solid #c7d2e3;border-radius:7px;padding:9px;background:#fff;font:inherit}}@media(max-width:1080px){{body{{grid-template-columns:1fr}}.sidebar{{display:none}}main{{padding:28px 24px}}}}@media(max-width:640px){{main{{padding:22px 14px}}.card-grid,.grid{{grid-template-columns:1fr}}h1{{font-size:26px}}.section-card{{padding:17px}}}}
</style></head><body><aside class='sidebar'><div><div class='brand'>Applicant Zero<span>Job search workspace</span></div><nav>{_workspace_navigation(active)}</nav></div><p class='privacy'>Your candidate profile, answers, résumés and tracker stay in the private local runtime.</p></aside><main><header><p class='eyebrow'>{html.escape(kicker)}</p><h1>{html.escape(title)}</h1><p class='lead'>{html.escape(subtitle)}</p></header>{content}</main></body></html>"""


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
        ("Current roles", str(len(relevant))),
        ("Strong matches", str(sum(row["recommendation"] == "Strong apply" for row in current_rows))),
        ("Ready to prepare", str(sum(row["workflow_status"] in {"New", "Saved"} for row in relevant))),
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


def _priority_panel(database_path: Path, rows: list[dict], followups: list[dict]) -> str:
    """Present one concise, actionable plan above the full review table."""
    roles = operational_queue(database_path, limit=3)
    healthy, refresh_message = discovery_log_status(database_path.parent.parent)
    role_rows = "".join(
        f"<li><a href='/brief?{urlencode({'external_id': role.external_id})}'>{html.escape(role.title)}</a><span>{html.escape(role.company)} · {html.escape(role.next_action)}</span></li>"
        for role in roles
    ) or "<li><strong>No current role needs preparation.</strong><span>Refresh discovery or import a suitable listing.</span></li>"
    due = [item for item in followups if item["due_date"] <= datetime.now().date().isoformat() and item["status"] != "Completed"]
    followup_note = f"{len(due)} follow-up{'s' if len(due) != 1 else ''} due." if due else "No follow-ups due."
    health_class = "is-healthy" if healthy else "needs-attention"
    return f"""<section class='priority-panel'><div><p class='eyebrow'>Your next best actions</p><h2>Prepare the strongest roles first.</h2><p>Open a preparation brief, check the facts, download your tailored material, and apply personally when ready.</p><p><a class='panel-button' href='/operations'>Open preparation queue</a><a class='panel-link' href='/campaigns'>Adjust search campaigns</a></p></div><div><ol>{role_rows}</ol><p class='followup-note'>{html.escape(followup_note)}</p><p class='refresh-health {health_class}'>{html.escape(refresh_message)}</p></div></section>"""


def _campaign_summary(rows: list[dict], project_root: Path) -> str:
    """Show which broad searches are on and their current relevant result count."""
    current = [row for row in rows if row["is_active"] and row["recommendation"] in {"Strong apply", "Apply", "Review"}]
    cards = []
    for campaign in load_campaigns(project_root):
        count = sum(row.get("lane") in campaign.role_lanes for row in current)
        state = "Active" if campaign.active else "Paused"
        cards.append(f"<li><strong>{html.escape(campaign.label)}</strong><span>{state} · {count} current role{'s' if count != 1 else ''}</span></li>")
    return f"<section class='campaign-summary'><div><p class='eyebrow'>Discovery focus</p><h2>Role lanes</h2><p>These switches control what future refreshes treat as relevant.</p></div><ul>{''.join(cards)}</ul><a href='/campaigns'>Manage campaigns</a></section>"


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
        route_labels = {"assisted": "Direct listing", "pilot": "Hosted listing", "login_required": "Login likely", "complex": "Multi-step", "manual_review": "Check listing"}
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
    priority_panel = _priority_panel(database_path, rows, followups)
    campaign_summary = _campaign_summary(rows, database_path.parent.parent)
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
.priority-panel{{display:grid;grid-template-columns:minmax(280px,.9fr) minmax(0,1.1fr);gap:28px;align-items:start;background:linear-gradient(135deg,#163b67,#1c4d85);color:#fff;border-radius:12px;padding:24px 26px;margin:22px 0;box-shadow:0 4px 14px #ced8e6}}.priority-panel h2{{font-size:22px;line-height:1.25;margin:0}}.priority-panel p{{line-height:1.5;color:#d7e6f8}}.priority-panel .eyebrow,.campaign-summary .eyebrow{{font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:.09em;margin:0 0 8px;color:#bcd6f4}}.priority-panel ol{{margin:3px 0;padding-left:22px}}.priority-panel li{{padding:0 0 11px 5px;line-height:1.4}}.priority-panel li a{{color:#fff;text-decoration:underline;text-underline-offset:3px}}.priority-panel li span{{display:block;color:#d7e6f8;font-size:13px;margin-top:2px}}.panel-button{{display:inline-block;padding:10px 13px;border-radius:7px;background:#fff;color:#163b67;font-weight:800;margin:2px 10px 2px 0}}.panel-link{{color:#fff;text-decoration:underline;text-underline-offset:3px}}.followup-note{{font-weight:700;margin:6px 0}}.refresh-health{{padding:9px 11px;border-radius:7px;font-size:13px}}.refresh-health.is-healthy{{background:#d9f3e6;color:#12643b}}.refresh-health.needs-attention{{background:#fff1cc;color:#8a5a00}}
.campaign-summary{{display:grid;grid-template-columns:220px minmax(0,1fr) auto;gap:20px;align-items:center;background:#fff;border:1px solid var(--border);border-radius:12px;padding:18px 22px;margin:18px 0;box-shadow:0 4px 16px rgba(15,48,82,.04)}}.campaign-summary h2{{font-size:18px;color:var(--navy);margin:0}}.campaign-summary p{{color:var(--muted);font-size:13px;line-height:1.45;margin:6px 0 0}}.campaign-summary .eyebrow{{color:var(--blue)}}.campaign-summary ul{{display:grid;grid-template-columns:repeat(2,minmax(160px,1fr));gap:8px 16px;list-style:none;padding:0;margin:0}}.campaign-summary li{{border-left:3px solid #c9ddf4;padding-left:9px}}.campaign-summary li strong,.campaign-summary li span{{display:block;font-size:13px}}.campaign-summary li strong{{color:var(--navy)}}.campaign-summary li span{{color:var(--muted);margin-top:2px}}.campaign-summary a{{white-space:nowrap}}
.table-wrap{{overflow-x:auto;background:#fff;border-radius:8px;box-shadow:0 1px 4px var(--border)}}table{{width:100%;border-collapse:collapse;min-width:1100px}} th{{text-align:left;background:#eaf0f8;color:var(--navy);padding:12px}} td{{padding:12px;border-top:1px solid #e5eaf1;vertical-align:top;font-size:14px;line-height:1.4}} a{{color:var(--blue);font-weight:bold;text-decoration:none}} small{{display:block;color:var(--muted);margin-top:4px}} form{{display:flex;gap:6px;flex-wrap:wrap;align-items:center}} form input[name=notes]{{min-width:170px;flex:1}} .badge,.listing-closed,.route{{display:inline-block;padding:3px 8px;border-radius:12px;font-weight:bold;font-size:12px}} .listing-closed{{display:block;width:max-content;background:#f1f3f5;color:#596273;margin-top:5px}} .route{{margin-top:6px;background:#eef4ff;color:#344c72}} .route-assisted{{background:#d9f3e6;color:#12643b}} .route-login_required,.route-complex{{background:#fff1cc;color:#8a5a00}} .strong-apply{{background:#d9f3e6;color:#12643b}} .apply{{background:#dceeff;color:#15588a}} .review{{background:#fff1cc;color:#8a5a00}} .skip{{background:#f1f3f5;color:#596273}} #no-results{{display:none;background:#fff;padding:28px;text-align:center;color:var(--muted);border-radius:8px}}
@media(max-width:1080px){{body{{grid-template-columns:1fr}}.sidebar{{display:none}}main{{padding:26px}}.insight-grid{{grid-template-columns:repeat(3,1fr)}}.priority-panel,.campaign-summary{{grid-template-columns:1fr}}}}@media(max-width:520px){{main{{padding:18px 14px}}.insight-grid{{grid-template-columns:1fr 1fr;gap:8px}}.insight{{padding:12px}}.priority-panel,.campaign-summary{{padding:18px}}.campaign-summary ul{{grid-template-columns:1fr}}.import-form{{grid-template-columns:1fr}}h1{{font-size:26px}}}}
</style></head><body><aside class='sidebar'><div><div class='brand'>Applicant Zero<span>Job search workspace</span></div><nav><a class='active' href='/'>Review queue</a><a href='/campaigns'>Search campaigns</a><a href='/operations'>Preparation queue</a><a href='/discovery'>Discovery coverage</a><a href='/answers'>Application answers</a><a href='/email-updates'>Email updates</a><a href='/outcomes'>Search progress</a><a href='/health'>System health</a><a href='/guide'>How to use this</a></nav></div><p class='privacy'>Your candidate profile, answers, résumés and tracker stay in the private local runtime.</p></aside><main><header class='page-header'><div><p class='header-kicker'>Sydney job search</p><h1>Review queue</h1><p class='subtitle'>Find relevant roles, prepare truthful materials, track your personal applications and keep the whole search organised.</p></div></header>{insights}
{priority_panel}
{campaign_summary}
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


def build_email_page(database_path: Path, sync_message: str = "") -> str:
    """Show local, read-only Gmail matching results without exposing mail bodies."""
    project_root = database_path.parent.parent
    connected, setup_message = gmail_setup_status(project_root)
    if database_path.exists():
        with sqlite3.connect(database_path) as connection:
            latest = latest_email_sync_run(connection)
            events = list_email_events(connection)
    else:
        latest = None
        events = []
    status = "Connected" if connected else "Setup needed"
    latest_text = "No Gmail sync has run yet."
    if latest:
        latest_text = (
            f"Last sync: {latest['completed_at']} · {latest['fetched_count']} new messages recorded · "
            f"{latest['matched_count']} matched · {latest['updated_count']} tracker updates."
        )
    rows = "".join(
        f"<tr><td>{html.escape(event['category'].title())}</td><td>{html.escape(event['company'] or 'No confident match')}</td><td>{html.escape(event['title'] or '')}</td><td>{html.escape(event['subject'] or 'No subject')}</td><td>{html.escape(event['confidence'])}</td><td>{'Yes' if event['tracker_updated'] else 'No'}</td></tr>"
        for event in events
    ) or "<tr><td colspan='6'>No job-related email metadata has been recorded yet.</td></tr>"
    sync_notice = f"<p class='notice'>{html.escape(sync_message)}</p>" if sync_message else ""
    sync_control = ""
    if connected:
        sync_control = (
            "<form method='post' action='/gmail-sync'><button type='submit'>"
            "Check the latest two days of job email</button></form>"
            "<p class='muted'>This reads email only. It never sends, labels, archives, deletes or changes any Gmail message.</p>"
        )
    return f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Applicant Zero - Email updates</title><style>:root{{--navy:#163b67;--border:#dce3ee;--muted:#667085}}*{{box-sizing:border-box}}body{{font-family:Arial,sans-serif;background:#f5f7fb;color:#182230;margin:0}}main{{max-width:1120px;margin:0 auto;padding:36px 24px}}h1,h2{{color:var(--navy)}}a{{color:#1261a0;font-weight:bold}}section{{background:#fff;border-radius:10px;padding:20px;margin:16px 0;box-shadow:0 1px 4px var(--border);line-height:1.55}}.status{{display:inline-block;padding:5px 9px;border-radius:12px;background:#eaf2fd;color:#15588a;font-weight:bold;font-size:13px}}.notice{{background:#d9f3e6;color:#12643b;padding:10px;border-radius:7px}}.note{{background:#eaf2fd;border-left:4px solid #1468b3}}button{{background:var(--navy);color:#fff;border:0;border-radius:7px;padding:10px 14px;font-weight:bold;cursor:pointer}}code{{display:block;background:#f4f7fb;padding:10px;border-radius:6px;white-space:pre-wrap}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;text-align:left;border-top:1px solid var(--border);vertical-align:top}}th{{color:var(--navy)}}.muted{{color:var(--muted)}}.table-wrap{{overflow:auto}}</style></head><body><main><p><a href='/'>← Return to review queue</a></p><h1>Email updates</h1><p>Optional read-only matching for a dedicated job-search Gmail inbox. Applicant Zero never sends, deletes, archives, labels or changes Gmail messages.</p><section><p><span class='status'>{status}</span></p><p>{html.escape(setup_message)}</p><p class='muted'>{html.escape(latest_text)}</p>{sync_notice}{sync_control}</section><section class='note'><h2>One-time setup</h2><ol><li>Create a separate Gmail address for job applications when ready.</li><li>In Google Cloud, create a Desktop OAuth client, enable Gmail API, then save its downloaded JSON as <code>private/gmail_client_secret.json</code>.</li><li>Install the optional local connector once:</li></ol><code>python -m pip install -e ".[gmail]"</code><p>Then run this in the project terminal:</p><code>$env:PYTHONPATH = "src"
python -m applicant_zero --gmail-connect</code><p>Google opens its own sign-in and consent window. Applicant Zero requests only <code>gmail.readonly</code>. The private token stays on this computer.</p><p>After that, run a two-day read-only check whenever you want:</p><code>python -m applicant_zero --gmail-sync</code></section><section><h2>Recorded job email updates</h2><p class='muted'>Only sender, subject, message id and the matching outcome are saved locally. Message bodies are used only in memory to classify the current sync and are not stored.</p><div class='table-wrap'><table><thead><tr><th>Type</th><th>Company</th><th>Role</th><th>Subject</th><th>Match</th><th>Tracker updated</th></tr></thead><tbody>{rows}</tbody></table></div></section></main></body></html>"""


def build_guide_page() -> str:
    """Plain-language operating guide available inside the local dashboard."""
    steps = (
        ("1. Refresh jobs", "Run the scheduled refresh or open Discovery coverage to see what sources were checked."),
        ("2. Review the queue", "Use the score, role lane and current-listing filters. Import a job you find on another website when it looks promising."),
        ("3. Prepare a role", "Open Prepare application. Applicant Zero creates private evidence and a Word working copy without changing your approved originals."),
        ("4. Check the facts", "Use the readiness checklist and AI review only as a draft. Resolve any missing evidence or eligibility condition before using the material."),
        ("5. Apply personally", "Open the original listing with your prepared résumé and cover letter. Applicant Zero does not interact with employer forms."),
        ("6. Record the outcome", "Mark the role Applied immediately after submitting. Later update Interview, Offer, Rejected or Closed and complete any follow-up reminder."),
    )
    cards = "".join(f"<article><h2>{html.escape(title)}</h2><p>{html.escape(detail)}</p></article>" for title, detail in steps)
    return f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Applicant Zero - How to use this</title><style>:root{{--navy:#123154;--border:#dbe5f1;--muted:#64748b;--canvas:#f4f7fb}}*{{box-sizing:border-box}}body{{font-family:Inter,Segoe UI,Arial,sans-serif;background:var(--canvas);color:#1e293b;margin:0}}main{{max-width:940px;margin:0 auto;padding:38px 24px}}a{{color:#1468b3;font-weight:700}}h1,h2{{color:var(--navy)}}h1{{font-size:32px;margin-bottom:8px}}.lead{{color:var(--muted);line-height:1.55;font-size:17px}}.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-top:24px}}article{{background:#fff;border:1px solid var(--border);border-radius:12px;padding:20px;box-shadow:0 4px 16px rgba(15,48,82,.04)}}article h2{{font-size:18px;margin:0 0 8px}}article p{{margin:0;line-height:1.55}}.note{{margin-top:18px;padding:17px 20px;background:#163b67;color:#fff;border-radius:12px;line-height:1.55}}@media(max-width:640px){{.grid{{grid-template-columns:1fr}}}}</style></head><body><main><p><a href='/'>← Return to review queue</a></p><h1>How to use Applicant Zero</h1><p class='lead'>This is your local job-search workspace. It discovers permitted listings, organises your evidence and helps you prepare each application. You keep control of every employer-facing decision.</p><section class='grid'>{cards}</section><section class='note'><strong>What stays with you:</strong> passwords, account creation, CAPTCHA, verification codes, protected eligibility or identity answers, unknown questions, and the final employer submission.</section></main></body></html>"""


def build_campaigns_page(database_path: Path) -> str:
    """Allow the candidate to turn broad role groups on or off before refresh."""
    project_root = database_path.parent.parent
    campaigns = load_campaigns(project_root)
    allocation = campaign_query_allocation(project_root)
    query_status = discovery_query_status(project_root)
    next_allocation: dict[str, int] = {}
    for identifier, _, _ in query_status["planned"]:
        next_allocation[identifier] = next_allocation.get(identifier, 0) + 1
    rows = "".join(
        f"<article class='section-card'><label><input type='checkbox' name='campaign' value='{html.escape(campaign.identifier, quote=True)}'{' checked' if campaign.active else ''}> <strong>{html.escape(campaign.label)}</strong></label><p>{html.escape(campaign.description)}</p><small>Role lanes: {html.escape(', '.join(lane.replace('_', ' ') for lane in campaign.role_lanes))}</small><p class='queries'>Search terms: {html.escape(' · '.join(campaign.queries))}</p><p class='allocation'>{'Next refresh: ' + str(next_allocation.get(campaign.identifier, 0)) + ' broad-feed search' + ('es' if next_allocation.get(campaign.identifier, 0) != 1 else '') + ' · standard cycle allocation: ' + str(allocation.get(campaign.identifier, 0)) if campaign.active else 'Paused: no broad-feed calls reserved.'}</p></article>"
        for campaign in campaigns
    )
    content = f"""<p class='notice'>Sydney and NSW are searched separately. Each refresh shares its broad-feed calls across active campaigns and rotates through the full active vocabulary instead of repeatedly searching the first few phrases. This computer is configured for up to {query_status['daily_limit']} broad-feed calls per day; {query_status['remaining_today']} remain today, and the next slice contains {len(query_status['planned'])} calls.</p><form method='post' action='/campaigns'><section class='grid'>{rows}</section><p><button type='submit'>Save discovery campaigns</button></p></form>"""
    return _workspace_page(
        "campaigns", "Discovery control", "Search campaigns",
        "Choose the role groups included in future discovery runs. Your choice stays private on this computer.", content,
    )
    return f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Applicant Zero - Search campaigns</title><style>:root{{--navy:#123154;--border:#dbe5f1;--muted:#64748b;--canvas:#f4f7fb}}*{{box-sizing:border-box}}body{{font-family:Inter,Segoe UI,Arial,sans-serif;background:var(--canvas);color:#1e293b;margin:0}}main{{max-width:980px;margin:0 auto;padding:38px 24px}}a{{color:#1468b3;font-weight:700}}h1,h2{{color:var(--navy)}}.lead{{color:var(--muted);line-height:1.55}}.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:24px 0}}article{{background:#fff;border:1px solid var(--border);border-radius:12px;padding:20px;box-shadow:0 4px 16px rgba(15,48,82,.04)}}label{{color:var(--navy);font-size:17px;cursor:pointer}}input{{width:18px;height:18px;vertical-align:-3px;margin-right:7px}}p{{line-height:1.5}}small,.queries{{display:block;color:var(--muted);font-size:13px}}.allocation{{font-weight:700;color:#15588a;font-size:13px}}button{{background:var(--navy);color:#fff;border:0;border-radius:7px;padding:11px 16px;font-weight:bold;cursor:pointer}}.note{{background:#eaf2fd;border-left:4px solid #1468b3;padding:15px 17px;border-radius:7px;line-height:1.5}}@media(max-width:640px){{.grid{{grid-template-columns:1fr}}}}</style></head><body><main><p><a href='/'>← Return to review queue</a></p><h1>Search campaigns</h1><p class='lead'>Choose the role groups to include in future daily discovery refreshes. The selected groups also control which role lanes are treated as relevant. Your choice stays private on this computer.</p><p class='note'>Sydney and NSW are searched separately. A capped refresh now shares its broad-feed calls across every active campaign, rather than letting the first campaign consume the whole budget. Listings that say only “NSW” are kept for review so you can confirm their real workplace instead of losing a possible Sydney role.</p><form method='post' action='/campaigns'><section class='grid'>{rows}</section><button type='submit'>Save discovery campaigns</button></form></main></body></html>"""


def build_operations_page(database_path: Path, prepared_count: int = 0) -> str:
    roles = operational_queue(database_path)
    eligible = [role for role in roles if role.eligible_for_bulk_prepare]
    rows = "".join(
        f"<article class='section-card'><h2>{html.escape(role.title)}</h2><p>{html.escape(role.company)} · {html.escape(role.recommendation)} · fit {role.score} · daily priority {role.daily_priority} · {html.escape(role.application_effort)} effort · {html.escape(role.workflow_status)}</p><p>{html.escape(role.next_action)}</p><p class='{'success' if role.eligible_for_bulk_prepare else 'notice'}'>{'Ready for local preparation' if role.eligible_for_bulk_prepare else 'Evidence to check: ' + (', '.join(role.blockers) or 'role-specific fit')}</p><a href='/brief?{urlencode({'external_id': role.external_id})}'>Open preparation brief</a></article>"
        for role in roles
    ) or "<article class='section-card'><h2>No current roles need action.</h2><p>Run discovery or import a suitable listing.</p></article>"
    success = f"<p class='success'>{prepared_count} role{'s' if prepared_count != 1 else ''} moved to Preparing with local materials created.</p>" if prepared_count else ""
    content = f"""{success}<section class='section-card'><h2>Ready now</h2><p><strong>{len(eligible)}</strong> role{'s' if len(eligible) != 1 else ''} can be prepared from your confirmed local materials.</p><form method='post' action='/prepare-eligible'><button type='submit'>Prepare up to three eligible roles</button></form></section><section>{rows}</section>"""
    return _workspace_page(
        "operations", "Application preparation", "Preparation queue",
        "Create local, truthful application materials for the roles you decide to pursue. No AI credit is used until you request an AI draft.", content,
    )
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>Applicant Zero - Preparation queue</title><style>body{{font-family:Arial,sans-serif;background:#f5f7fb;color:#182230;margin:0}}main{{max-width:900px;margin:0 auto;padding:32px}}h1,h2{{color:#163b67}}a{{color:#1261a0;font-weight:bold}}article,section{{background:#fff;border-radius:8px;padding:18px;margin:14px 0;box-shadow:0 1px 4px #dce3ee}}.ready,.success{{background:#d9f3e6;color:#12643b;padding:9px;border-radius:6px}}.blocked{{background:#fff1cc;color:#8a5a00;padding:9px;border-radius:6px}}button{{padding:10px 15px;border:0;border-radius:6px;background:#163b67;color:#fff;font-weight:bold;cursor:pointer}}</style></head><body><main><p><a href='/'>← Return to job queue</a></p><h1>Preparation queue</h1><p>This separates local preparation work from roles that need an evidence decision. Bulk preparation creates files only: no AI usage or employer contact.</p>{success}<section><h2>Ready now</h2><p><strong>{len(eligible)}</strong> role{'s' if len(eligible) != 1 else ''} can be prepared from your confirmed local materials.</p><form method='post' action='/prepare-eligible'><button type='submit'>Prepare up to three eligible roles</button></form></section><section><h2>Prioritised queue</h2>{rows}</section></main></body></html>"""


def build_discovery_page(database_path: Path, board_message: str = "") -> str:
    """Show direct public coverage, candidate-import routes and board onboarding."""
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
            board_trends, board_history = list_board_check_trends(connection)
    else:
        board_checks = []
        board_trends, board_history = {}, []
    board_health = board_health_summary(board_path, board_checks)
    employer_rows = employer_coverage_rows(
        PROJECT_ROOT / "data" / "target_companies.starter.json", board_path, board_checks, board_trends,
    )
    priority_rows = prioritise_targets(load_targets(PROJECT_ROOT / "data" / "target_companies.starter.json"), employer_rows)[:8]
    priority_list = "".join(
        f"<li><strong>{html.escape(item.company)}</strong> · P{item.priority} · {html.escape(item.action)}</li>"
        for item in priority_rows
    )
    def listing_summary(row: dict[str, object]) -> str:
        if not row["ats"]:
            return "—"
        if row["health"] != "checked":
            return "Source unavailable" if row["health"] == "unavailable" else "Not checked yet"
        if row["job_count"] is None:
            return "Checked before history tracking"
        change = row["job_change"]
        suffix = ""
        if change is not None:
            suffix = f" · {'+' if int(change) > 0 else ''}{int(change)} since previous check"
        return f"{int(row['job_count'])} public listing{'s' if int(row['job_count']) != 1 else ''}{suffix}"

    coverage_table = "".join(
        f"<tr><td>{html.escape(str(row['company']))}</td><td>{html.escape(str(row['sector']))}</td><td>P{row['priority']}</td><td><span class='{'auto' if row['ats'] else 'research'}'>{html.escape(str(row['route']))}{(' · ' + html.escape(str(row['ats']))) if row['ats'] else ''}</span></td><td><span class='{'auto' if row['health'] == 'checked' else 'research'}'>{html.escape(str(row['health']).replace('_', ' ').title())}</span></td><td>{html.escape(listing_summary(row))}</td></tr>"
        for row in employer_rows
    )
    history_table = "".join(
        f"<tr><td>{html.escape(str(row['checked_at']))}</td><td>{html.escape(str(row['company']))}</td><td>{html.escape(str(row['status']).replace('_', ' ').title())}</td><td>{row['job_count'] if row['status'] == 'checked' else '—'}</td><td>{html.escape(str(row['detail']) or 'Public board read completed.')}</td></tr>"
        for row in board_history[:12]
    ) or "<tr><td colspan='5'>No public-board check history has been recorded yet.</td></tr>"
    automated = "".join(f"<li>{html.escape(item)}</li>" for item in overview["automated_sources"])
    manual = "".join(f"<li>{html.escape(item)}</li>" for item in overview["manual_sources"])
    covered = " · ".join(html.escape(item) for item in overview["configured"]) or "None yet"
    waiting = " · ".join(html.escape(item) for item in overview["research_needed"][:20])
    more = max(0, len(overview["research_needed"]) - 20)
    if more:
        waiting += f" · and {more} more"
    message = f"<p class='success'>{html.escape(board_message)}</p>" if board_message else ""
    content = f"""{message}<section class='card-grid'><article class='metric'><strong>{overview['target_count']}</strong><span>target employers tracked</span></article><article class='metric'><strong>{overview['configured_count']}</strong><span>verified public career boards</span></article><article class='metric'><strong>{overview['source_count']}</strong><span>source routes recorded</span></article></section><section class='section-card'><h2>Add a public employer careers link</h2><p class='muted'>Paste the employer’s public Greenhouse, Lever, Ashby, SmartRecruiters or Workable careers URL. Applicant Zero identifies the provider and validates that it can read public listings before saving it. No login, password or API key is stored.</p><form method='post' action='/boards' class='grid'><label>Employer name<input name='company' required placeholder='e.g. Example Australia'></label><label>Public careers URL<input name='board_url' type='url' required placeholder='https://jobs.lever.co/example'></label><p><button type='submit'>Validate and add board</button></p></form></section><section class='grid'><article class='section-card'><h2>What to prioritise next</h2><ul>{priority_list}</ul></article><article class='section-card'><h2>Automatic refresh</h2><ul>{automated}</ul><p><strong>Current verified boards:</strong> {covered}</p><p class='muted'>{board_health['checked']} recently checked · {board_health['unavailable']} unavailable · {board_health['stale']} stale · {board_health['never_checked']} not checked yet.</p></article></section><section class='section-card'><h2>Recent public-board checks</h2><p class='muted'>Zero listings means the public board was read successfully and has no current listings. An unavailable result is a source issue, not a zero.</p><div class='table-wrap'><table><thead><tr><th>Checked</th><th>Employer</th><th>Result</th><th>Listings</th><th>Detail</th></tr></thead><tbody>{history_table}</tbody></table></div></section><section class='section-card'><h2>Candidate-assisted routes</h2><ul>{manual}</ul><p>When you find a relevant public listing on SEEK, LinkedIn, Indeed or another site, use <strong>Add a job from another website</strong> in the review queue. Applicant Zero will still score, prepare and track it locally.</p></section><section class='section-card'><h2>Employer-board research queue</h2><p>{waiting or 'All current targets are covered.'}</p><p class='muted'>Research queue means a target has been prioritised but no public, reliable board token has been recorded. It does not mean there is a vacancy.</p></section><section class='section-card'><h2>Employer coverage map</h2><p class='muted'>Public ATS refresh means the employer board is configured, not that it necessarily has a vacancy.</p><div class='table-wrap'><table><thead><tr><th>Employer</th><th>Sector</th><th>Priority</th><th>Discovery route</th><th>Latest check</th><th>Current public listings</th></tr></thead><tbody>{coverage_table}</tbody></table></div></section>"""
    return _workspace_page(
        "discovery", "Source coverage", "Discovery coverage",
        "See which public employer boards are being monitored, where discovery needs research, and what each verified source returned.", content,
    )
    return f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Applicant Zero - Discovery coverage</title><style>:root{{--navy:#163b67;--border:#dce3ee;--muted:#667085}}*{{box-sizing:border-box}}body{{font-family:Arial,sans-serif;background:#f5f7fb;color:#182230;margin:0}}main{{max-width:1100px;margin:0 auto;padding:36px 24px}}h1,h2{{color:var(--navy)}}a{{color:#1261a0;font-weight:bold}}.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:20px 0}}article,section{{background:#fff;border-radius:10px;padding:18px;box-shadow:0 1px 4px var(--border);margin:16px 0}}article strong{{font-size:28px;color:var(--navy);display:block}}article span,.muted{{color:var(--muted)}}li{{margin:7px 0}}.table-wrap{{overflow:auto}}table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;padding:10px;border-top:1px solid var(--border)}}th{{color:var(--navy);background:#eef4fb}}.auto,.research{{display:inline-block;padding:3px 8px;border-radius:12px;font-size:12px;font-weight:bold}}.auto{{background:#d9f3e6;color:#12643b}}.research{{background:#fff1cc;color:#8a5a00}}.success{{background:#d9f3e6;color:#12643b;padding:10px;border-radius:7px}}.board-form{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;align-items:end}}.board-form label{{font-weight:bold;font-size:13px;color:var(--navy)}}.board-form input,.board-form select{{display:block;width:100%;margin-top:5px;padding:9px;border:1px solid #c7d2e3;border-radius:6px;font:inherit}}button{{background:var(--navy);color:#fff;border:0;border-radius:7px;padding:10px 14px;font-weight:bold;cursor:pointer}}@media(max-width:650px){{.cards,.board-form{{grid-template-columns:1fr}}}}</style></head><body><main><p><a href='/'>← Return to job queue</a></p><h1>Discovery coverage</h1><p class='muted'>This is the operating map for your job search. A company is only added to automatic refresh after its public ATS board has been verified.</p>{message}<div class='cards'><article><strong>{overview['target_count']}</strong><span>target employers tracked</span></article><article><strong>{overview['configured_count']}</strong><span>verified public career boards</span></article><article><strong>{overview['source_count']}</strong><span>source routes recorded</span></article></div><section><h2>Add a verified public employer board</h2><p class='muted'>Use this only after you have opened the employer’s own public career page and can see it is hosted by Greenhouse, Lever, Ashby or SmartRecruiters. Enter the public board token from that URL. This saves no login, password or API key and reads listings only.</p><form method='post' action='/boards' class='board-form'><label>Employer name<input name='company' required placeholder='e.g. Example Australia'></label><label>Public ATS<select name='ats'><option value='greenhouse'>Greenhouse</option><option value='lever'>Lever</option><option value='ashby'>Ashby</option><option value='smartrecruiters'>SmartRecruiters</option></select></label><label>Public board token<input name='token' required placeholder='Token from the public careers URL'></label><button type='submit'>Add public board</button></form></section><section><h2>What to prioritise next</h2><ul>{priority_list}</ul></section><section><h2>Automatic refresh</h2><ul>{automated}</ul><p><strong>Current verified boards:</strong> {covered}</p><p class='muted'>{board_health['checked']} recently checked · {board_health['unavailable']} unavailable · {board_health['stale']} stale · {board_health['never_checked']} not checked yet.</p></section><section><h2>Recent public-board checks</h2><p class='muted'>A zero means the public board was read successfully and currently has no listings; an unavailable result is a source issue, not a zero.</p><div class='table-wrap'><table><thead><tr><th>Checked</th><th>Employer</th><th>Result</th><th>Listings</th><th>Detail</th></tr></thead><tbody>{history_table}</tbody></table></div></section><section><h2>Candidate-assisted routes</h2><ul>{manual}</ul><p>Use “Add a job from another website” when you find a suitable SEEK, LinkedIn or other listing. The same scoring, tailoring and tracking workflow then applies.</p></section><section><h2>Employer-board research queue</h2><p>{waiting or 'All current targets are covered.'}</p><p class='muted'>Research queue means a target has been prioritised but no public, reliable board token has been recorded yet. It does not mean there is a vacancy.</p></section><section><h2>Employer coverage map</h2><p class='muted'>Priority 1 employers are the first research group. Public ATS refresh means the board is configured; it does not promise a current vacancy. Latest check shows the result of the most recent local refresh.</p><div class='table-wrap'><table><thead><tr><th>Employer</th><th>Sector</th><th>Priority</th><th>Discovery route</th><th>Latest check</th><th>Current public listings</th></tr></thead><tbody>{coverage_table}</tbody></table></div></section></main></body></html>"""


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
    inventory_status = "<p class='help'>Create a private evidence inventory from your approved PDFs and any linked Word masters. It reads the files locally and never changes them.</p>"
    if inventory.exists():
        try:
            payload = json.loads(inventory.read_text(encoding="utf-8"))
            pdf_count = len(payload.get("resumes", {}))
            master_count = len(payload.get("editable_masters", {}))
            inventory_status = (
                "<p class='ready'>Private résumé evidence inventory is ready. "
                f"{pdf_count} approved PDF family{'ies' if pdf_count != 1 else ''} and "
                f"{master_count} editable Word master{'s' if master_count != 1 else ''} are available as source wording for tailored review.</p>"
            )
        except (json.JSONDecodeError, AttributeError):
            inventory_status = "<p class='help'>The private résumé evidence inventory needs to be refreshed before it can be used.</p>"
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
        ("Offers", str(summary["offers"])),
        ("Not selected", str(summary["rejected"])),
        ("Interview rate", f"{summary['interview_rate']:.1f}%"),
        ("Response rate", f"{summary['response_rate']:.1f}%"),
        ("Follow-ups due", str(summary["due_followups"])),
        ("In progress", str(summary["in_progress"])),
    )
    card_html = "".join(f"<article><strong>{html.escape(value)}</strong><span>{html.escape(label)}</span></article>" for label, value in cards)
    next_step = "Prepare your strongest current role." if summary["in_progress"] else "Review the current queue and prepare one suitable role."
    if summary["due_followups"]:
        next_step = "Complete the due follow-up before preparing another application."
    return f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Applicant Zero - Search progress</title><style>:root{{--navy:#163b67;--border:#dce3ee;--muted:#667085}}*{{box-sizing:border-box}}body{{font-family:Arial,sans-serif;background:#f5f7fb;color:#182230;margin:0}}main{{max-width:960px;margin:0 auto;padding:36px 24px}}h1,h2{{color:var(--navy)}}a{{color:#1261a0;font-weight:bold}}.cards{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:20px 0}}article,section{{background:#fff;border-radius:10px;padding:18px;box-shadow:0 1px 4px var(--border)}}article strong{{font-size:26px;color:var(--navy);display:block}}article span{{font-size:13px;color:var(--muted)}}section{{margin-top:18px;line-height:1.55}}.next{{background:#d9f3e6;color:#12643b}}@media(max-width:760px){{.cards{{grid-template-columns:repeat(2,1fr)}}}}@media(max-width:420px){{.cards{{grid-template-columns:1fr}}}}</style></head><body><main><p><a href='/'>← Return to job queue</a></p><h1>Search progress</h1><p>Private, local progress figures based only on roles you have recorded in Applicant Zero.</p><div class='cards'>{card_html}</div><section class='next'><h2>Next action</h2><p>{html.escape(next_step)}</p></section><section><h2>How to use these figures</h2><p>“Applications submitted” includes roles marked Applied, Interview, Offer, Rejected or Closed. The interview rate is interviews divided by submitted applications. The response rate is interviews plus offers divided by submitted applications. These figures do not infer employer responses and never send follow-ups automatically.</p><p><a href='/export-tracker'>Download the full tracker CSV</a> when you want to review details in Excel.</p></section></main></body></html>"""


def build_brief_page(database_path: Path, external_id: str) -> str:
    with sqlite3.connect(database_path) as connection:
        row = get_match(connection, external_id)
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
    intelligence = inspect_job(str(row["title"]), str(row["location"]), str(row["description"]))
    contact_html = "<br>".join(f"<a href='mailto:{html.escape(address, quote=True)}'>{html.escape(address)}</a>" for address in intelligence.contacts) or "No public contact email was detected in the imported listing."
    listing_intelligence = (
        f"<p><strong>Location:</strong> {html.escape(intelligence.location_signal)}</p>"
        f"<p><strong>Employment type:</strong> {html.escape(intelligence.employment_type)}</p>"
        f"<p><strong>Salary:</strong> {html.escape(intelligence.salary or 'Not stated in the imported listing.')}</p>"
        f"<p><strong>Closing information:</strong> {html.escape(intelligence.closing_detail or 'No closing date was detected; check the original listing.')}</p>"
        f"<p><strong>Contact:</strong> {contact_html}</p>"
    )
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
    verified_count = len([value for value in answer_library.get("verified_answers", {}).values() if value])
    confirmation_count = len([value for value in answer_library.get("answers_requiring_confirmation", {}).values() if not value])
    saved_draft = load_ai_draft(database_path, external_id)
    question_drafts = load_question_drafts(database_path, external_id)
    resume_review_button = f"<form method='post' action='/resume-review'><input type='hidden' name='external_id' value='{html.escape(external_id, quote=True)}'><button type='submit'>Create tailored resume review</button></form>"
    resume_copy_button = f"<form method='post' action='/resume-copy'><input type='hidden' name='external_id' value='{html.escape(external_id, quote=True)}'><button type='submit'>Create editable role copy</button></form>"
    manifest_button = f"<form method='post' action='/material-manifest'><input type='hidden' name='external_id' value='{html.escape(external_id, quote=True)}'><button type='submit'>Create evidence manifest</button></form>"
    preparation_bundle_button = f"<form method='post' action='/prepare-role'><input type='hidden' name='external_id' value='{html.escape(external_id, quote=True)}'><button type='submit'>Prepare role materials</button></form><p class='muted'>Creates the local evidence manifest, preparation packet and editable Word copy. It does not contact the employer or use AI credits.</p>"
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
<section class='card'><h2>Listing intelligence</h2>{listing_intelligence}</section>
<section class='card'><h2>Evidence you can use</h2><p>{html.escape(', '.join(evidence) or 'No direct skill match was identified; read the original listing carefully.')}</p><h2>Requirements to check</h2><p>{html.escape(', '.join(missing) or 'No additional named requirement was detected by the initial matcher.')}</p></section>
<section class='card'><h2>Application pack readiness</h2><p>Your private answer library currently has <strong>{verified_count}</strong> verified answers and <strong>{confirmation_count}</strong> items you may want to confirm before applying.</p><p>Prepare the material below, then open the original listing and complete the employer application yourself.</p></section>
<section class='card'><h2>Application readiness</h2><p class='{'ready' if ready_to_submit else 'notice'}'>{html.escape(readiness_status)}</p><ol>{readiness_rows}</ol><form method='post' action='/review-materials'><input type='hidden' name='external_id' value='{html.escape(external_id, quote=True)}'><input name='review_note' placeholder='Optional review note'><button type='submit'>Mark materials reviewed</button></form></section>
<section class='card'><h2>Application question workspace</h2><p>Paste an unfamiliar role-specific application question to produce a private review draft from your verified evidence. Visa, work-rights, identity and health questions remain for you to answer directly.</p><form method='post' action='/question-draft' class='stacked'><input type='hidden' name='external_id' value='{html.escape(external_id, quote=True)}'><label>Application question<textarea name='question' required placeholder='Paste the employer question here'></textarea></label><button type='submit'>Draft truthful response</button></form>{question_items}</section>
<section class='card'><h2>Prepare your application pack</h2><ol><li>Read the original listing and confirm eligibility, location and seniority.</li><li>Tailor only truthful résumé wording to the role’s real requirements.</li><li>Prepare a short, specific response for any application questions.</li><li>Open the original listing, apply personally, then mark the tracker Applied after the employer confirms submission.</li></ol>{preparation_bundle_button}{manifest_button}{manifest_status}<form method='post' action='/packet'><input type='hidden' name='external_id' value='{html.escape(external_id, quote=True)}'><button type='submit'>Save private application packet</button></form><p>After the private evidence library and OpenAI API key are set up, you can also generate a truthful AI review draft.</p><form method='post' action='/ai-draft'><input type='hidden' name='external_id' value='{html.escape(external_id, quote=True)}'><button type='submit'>Generate AI tailoring draft</button></form>{resume_review_button}{resume_copy_button}{resume_copy_status}</section>
<section class='card'><h2>After you submit</h2><p>Applicant Zero never submits for you. After the employer site confirms your submission, save one confirmation detail here to update the tracker.</p>{proof_html}</section>
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
            elif parsed.path == "/email-updates":
                message = parse_qs(parsed.query).get("sync", [""])[0]
                content = build_email_page(database_path, message).encode("utf-8")
            elif parsed.path == "/actions":
                content = build_actions_page(database_path).encode("utf-8")
            elif parsed.path == "/campaigns":
                content = build_campaigns_page(database_path).encode("utf-8")
            elif parsed.path == "/operations":
                prepared_count = int(parse_qs(parsed.query).get("prepared", ["0"])[0] or "0")
                content = build_operations_page(database_path, prepared_count).encode("utf-8")
            elif parsed.path == "/discovery":
                message = parse_qs(parsed.query).get("board", [""])[0]
                content = build_discovery_page(database_path, message).encode("utf-8")
            elif parsed.path == "/outcomes":
                content = build_outcomes_page(database_path).encode("utf-8")
            elif parsed.path == "/daily-digest":
                content = create_daily_digest(database_path).read_bytes()
            elif parsed.path == "/health":
                content = health_page(database_path.parent.parent).encode("utf-8")
            elif parsed.path == "/guide":
                content = build_guide_page().encode("utf-8")
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
            if self.path not in {"/update", "/packet", "/ai-draft", "/answers", "/resume-inventory", "/import", "/resume-review", "/resume-copy", "/material-manifest", "/prepare-role", "/prepare-eligible", "/review-materials", "/submission-proof", "/question-draft", "/complete-followup", "/complete-action", "/platform-pilot", "/campaigns", "/gmail-sync", "/boards"}:
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", "0"))
            values = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
            external_id = values.get("external_id", [""])[0]
            if self.path == "/gmail-sync":
                try:
                    result = sync_gmail(database_path.parent.parent, database_path)
                    message = f"Read-only check complete: {result['fetched']} new message(s), {result['matched']} matched, {result['updated']} tracker update(s)."
                except GmailSetupError as error:
                    message = f"Read-only Gmail check did not run: {error}"
                self.send_response(303)
                self.send_header("Location", "/email-updates?" + urlencode({"sync": message}))
                self.end_headers()
                return
            if self.path == "/boards":
                try:
                    company = values.get("company", [""])[0]
                    board_url = values.get("board_url", [""])[0]
                    ats, token = public_board_from_url(board_url)
                    public_jobs = fetch_public_board(company.strip(), ats, token)
                    entry, created = add_public_board_url(
                        database_path.parent.parent,
                        PROJECT_ROOT / "data" / "company_boards.starter.json",
                        company,
                        board_url,
                    )
                    message = (
                        f"Validated {len(public_jobs)} public listing(s) and added {entry['company']} to the private board registry."
                        if created else f"Validated {len(public_jobs)} public listing(s). That board is already saved as {entry['company']}."
                    )
                except (OSError, ValueError, KeyError, TypeError) as error:
                    message = f"Public board was not added: {error}"
                self.send_response(303)
                self.send_header("Location", "/discovery?" + urlencode({"board": message}))
                self.end_headers()
                return
            if self.path == "/campaigns":
                save_enabled_campaigns(database_path.parent.parent, set(values.get("campaign", [])))
                self.send_response(303)
                self.send_header("Location", "/campaigns")
                self.end_headers()
                return
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
