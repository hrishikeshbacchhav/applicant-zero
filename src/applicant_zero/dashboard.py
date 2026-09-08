import html
import json
import sqlite3
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from .storage import WORKFLOW_STATUSES, list_matches, update_workflow


def _badge(recommendation: str) -> str:
    css_class = recommendation.lower().replace(" ", "-")
    return f'<span class="badge {css_class}">{html.escape(recommendation)}</span>'


def build_page(database_path: Path) -> str:
    if not database_path.exists():
        rows: list[dict] = []
    else:
        with sqlite3.connect(database_path) as connection:
            rows = list_matches(connection)

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
        table_rows.append(
            f"<tr data-status='{html.escape(row['recommendation'])}'>"
            f"<td><a href='{link}' target='_blank' rel='noreferrer'>{title}</a><small>{html.escape(row['company'])}</small></td>"
            f"<td>{html.escape(row['location'])}<small>{html.escape(row['source'])}</small></td>"
            f"<td>{_badge(row['recommendation'])}<small>Score: {row['score']}</small></td>"
            f"<td>{html.escape(row['resume_family'] or 'Not recommended')}</td>"
            f"<td>{reasons}</td>"
            f"<td><form method='post' action='/update'><input type='hidden' name='external_id' value='{job_id}'>"
            f"<select name='workflow_status'>{status_options}</select><input name='notes' value='{notes}' placeholder='Your note'><button type='submit'>Save</button></form></td></tr>"
        )

    body = "".join(table_rows) or "<tr><td colspan='5'>No jobs collected yet. Run a discovery source first.</td></tr>"
    return f"""<!doctype html>
<html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>
<title>Applicant Zero - Review queue</title>
<style>
body{{font-family:Arial,sans-serif;background:#f5f7fb;color:#182230;margin:0}} main{{max-width:1280px;margin:0 auto;padding:32px}}
h1{{margin:0;color:#163b67}} .subtitle{{color:#5e6c84;margin:7px 0 24px}} .filters{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}}
button{{border:1px solid #c7d2e3;border-radius:5px;background:#fff;padding:8px 12px;cursor:pointer}} button.active{{background:#163b67;color:#fff}}
table{{width:100%;border-collapse:collapse;background:#fff;box-shadow:0 1px 4px #dce3ee}} th{{text-align:left;background:#eaf0f8;color:#163b67;padding:12px}} td{{padding:12px;border-top:1px solid #e5eaf1;vertical-align:top;font-size:14px;line-height:1.4}} a{{color:#1261a0;font-weight:bold;text-decoration:none}} small{{display:block;color:#667085;margin-top:4px}} .badge{{display:inline-block;padding:3px 8px;border-radius:12px;font-weight:bold;font-size:12px}} .strong-apply{{background:#d9f3e6;color:#12643b}} .apply{{background:#dceeff;color:#15588a}} .review{{background:#fff1cc;color:#8a5a00}} .skip{{background:#f1f3f5;color:#596273}}
</style></head><body><main><h1>Applicant Zero</h1><p class='subtitle'>Local job review queue. Opening a link does not submit an application.</p>
<div class='filters'><button class='active' onclick="filterRows('All',this)">All</button><button onclick="filterRows('Strong apply',this)">Strong apply</button><button onclick="filterRows('Apply',this)">Apply</button><button onclick="filterRows('Review',this)">Review</button><button onclick="filterRows('Skip',this)">Skip</button></div>
<table><thead><tr><th>Role</th><th>Location / source</th><th>Recommendation</th><th>Résumé</th><th>Why</th><th>Your tracker</th></tr></thead><tbody>{body}</tbody></table>
</main><script>function filterRows(status,button){{document.querySelectorAll('tbody tr').forEach(row=>row.style.display=status==='All'||row.dataset.status===status?'':'none');document.querySelectorAll('button').forEach(b=>b.classList.remove('active'));button.classList.add('active')}}</script></body></html>"""


def serve(database_path: Path, port: int = 8765) -> None:
    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/":
                self.send_error(404)
                return
            content = build_page(database_path).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        def do_POST(self):
            if self.path != "/update":
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", "0"))
            values = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
            external_id = values.get("external_id", [""])[0]
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
