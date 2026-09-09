import argparse
import json
from pathlib import Path

from .ai_drafting import check_tailoring_setup
from .daily_digest import create_daily_digest
from .dashboard import serve
from .private_profile import check_profile
from .profile import RISHI_PROFILE
from .scoring import Job, score_job
from .sources.adzuna import fetch_jobs, fetch_query_batch
from .sources.company_boards import fetch_company_boards_with_report
from .storage import initialise_database, mark_company_jobs_inactive, record_refresh_run, save_board_checks, save_match

ROOT = Path(__file__).resolve().parents[2]


def _save_jobs(database, jobs: list[Job], show_all: bool = False) -> list[tuple[Job, object]]:
    queue = []
    for job in jobs:
        result = score_job(job, RISHI_PROFILE)
        save_match(database, job, result)
        queue.append((job, result))
    return queue if show_all else [(job, result) for job, result in queue if result.recommendation != "Skip"]


def _board_path() -> Path:
    private = ROOT / "data" / "company_boards.json"
    return private if private.exists() else ROOT / "data" / "company_boards.starter.json"


def run_daily_refresh(max_queries: int | None = None) -> tuple[int, int, str]:
    """Refresh public boards and a capped query batch as one daily run."""
    board_jobs, reports = fetch_company_boards_with_report(_board_path())
    query_file = ROOT / "data" / "search_queries.json"
    if not query_file.exists():
        query_file = ROOT / "data" / "search_queries.starter.json"
    config = json.loads(query_file.read_text(encoding="utf-8"))
    queries = config.get("queries", [])
    query_jobs, query_errors = fetch_query_batch(ROOT, queries, config.get("location", "Sydney"), max_queries)
    jobs = list({job.external_id: job for job in [*board_jobs, *query_jobs]}.values())
    database = initialise_database(ROOT / "data" / "applicant_zero.sqlite3")
    save_board_checks(database, reports)
    visible = _save_jobs(database, jobs)
    for report in reports:
        if report.status == "checked":
            mark_company_jobs_inactive(database, report.company, [job.external_id for job in board_jobs if job.company == report.company])
    checked = sum(report.status == "checked" for report in reports)
    unavailable = sum(report.status == "unavailable" for report in reports)
    query_total = min(len(queries), max_queries or len(queries))
    detail = f"{checked} company boards checked; {query_total} Sydney search queries run"
    if query_errors:
        detail += f"; {len(query_errors)} query source issue(s) skipped"
    record_refresh_run(database, "Daily discovery refresh", len(jobs), len(visible), checked, unavailable, detail)
    return len(jobs), len(visible), detail


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank job listings for Applicant Zero.")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--adzuna", action="store_true")
    parser.add_argument("--company-boards", type=Path)
    parser.add_argument("--daily-refresh", action="store_true")
    parser.add_argument("--daily-digest", action="store_true")
    parser.add_argument("--max-queries", type=int)
    parser.add_argument("--query", default="data analyst")
    parser.add_argument("--where", default="Sydney")
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--dashboard", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--show-all", action="store_true")
    parser.add_argument("--profile-check", action="store_true")
    parser.add_argument("--tailoring-check", action="store_true")
    args = parser.parse_args()
    source_count = int(args.demo) + int(args.adzuna) + int(args.company_boards is not None) + int(args.daily_refresh) + int(args.daily_digest)
    if args.profile_check:
        if source_count or args.dashboard: parser.error("Use --profile-check on its own.")
        issues = check_profile(ROOT / "private" / "candidate_profile.json")
        print("Your private profile still needs:" if issues else "Your private candidate profile is ready for application preparation.")
        for issue in issues: print(f"- {issue}")
        return
    if args.tailoring_check:
        if source_count or args.dashboard: parser.error("Use --tailoring-check on its own.")
        issues = check_tailoring_setup(ROOT)
        print("AI tailoring still needs:" if issues else "AI tailoring files are ready and an API key value is present. The key is verified only when you generate the first review draft.")
        for issue in issues: print(f"- {issue}")
        return
    if args.dashboard:
        if source_count: parser.error("Use --dashboard on its own.")
        serve(ROOT / "data" / "applicant_zero.sqlite3", args.port)
        return
    if args.daily_digest:
        if source_count != 1: parser.error("Use --daily-digest on its own.")
        print(f"Daily priority digest created: {create_daily_digest(ROOT / 'data' / 'applicant_zero.sqlite3')}")
        return
    if args.daily_refresh:
        if source_count != 1: parser.error("Use --daily-refresh on its own.")
        collected, relevant, detail = run_daily_refresh(args.max_queries)
        print(f"Daily refresh complete: {collected} roles collected; {relevant} worth reviewing. {detail}.")
        return
    if source_count != 1: parser.error("Choose exactly one source: --demo, --adzuna, --company-boards, --daily-refresh, --daily-digest or --dashboard.")
    reports = []
    if args.demo:
        jobs = [Job(**record) for record in json.loads((ROOT / "data" / "demo_jobs.json").read_text(encoding="utf-8"))]
    elif args.adzuna:
        jobs = fetch_jobs(ROOT, args.query, args.where, args.page)
    else:
        jobs, reports = fetch_company_boards_with_report(args.company_boards)
        print(f"Career boards checked: {sum(report.status == 'checked' for report in reports)}. Unavailable boards skipped: {sum(report.status == 'unavailable' for report in reports)}.")
    database = initialise_database(ROOT / "data" / "applicant_zero.sqlite3")
    if args.company_boards: save_board_checks(database, reports)
    visible = _save_jobs(database, jobs, args.show_all)
    if args.company_boards:
        for report in reports:
            if report.status == "checked": mark_company_jobs_inactive(database, report.company, [job.external_id for job in jobs if job.company == report.company])
        record_refresh_run(database, "Company career boards", len(jobs), len(visible), sum(report.status == "checked" for report in reports), sum(report.status == "unavailable" for report in reports))
    elif args.adzuna:
        record_refresh_run(database, "Adzuna", len(jobs), len(visible))
    print(f"Collected {len(jobs)} roles. Showing {len(visible)} roles worth reviewing; use the dashboard for the full record.")


if __name__ == "__main__":
    main()
