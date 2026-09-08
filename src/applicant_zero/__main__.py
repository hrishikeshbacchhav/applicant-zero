import argparse
import json
from pathlib import Path

from .profile import RISHI_PROFILE
from .scoring import Job, score_job
from .storage import initialise_database, mark_company_jobs_inactive, save_board_checks, save_match
from .sources.adzuna import fetch_jobs
from .sources.company_boards import fetch_company_boards_with_report
from .dashboard import serve
from .ai_drafting import check_tailoring_setup
from .private_profile import check_profile


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank job listings for Applicant Zero.")
    parser.add_argument("--demo", action="store_true", help="Import the safe demo job feed.")
    parser.add_argument("--adzuna", action="store_true", help="Search Adzuna's official Australian job API.")
    parser.add_argument("--company-boards", type=Path, help="Read public Greenhouse and Lever boards listed in a JSON file.")
    parser.add_argument("--query", default="data analyst", help="Job title or skill query for Adzuna.")
    parser.add_argument("--where", default="Sydney", help="Location query for Adzuna.")
    parser.add_argument("--page", type=int, default=1, help="Adzuna results page.")
    parser.add_argument("--dashboard", action="store_true", help="Open the local job review dashboard.")
    parser.add_argument("--port", type=int, default=8765, help="Local dashboard port.")
    parser.add_argument("--show-all", action="store_true", help="Also show jobs that were skipped as outside the target search.")
    parser.add_argument("--profile-check", action="store_true", help="Check whether the private candidate profile is ready for application preparation.")
    parser.add_argument("--tailoring-check", action="store_true", help="Check whether private evidence and optional AI drafting are ready.")
    args = parser.parse_args()
    source_count = int(args.demo) + int(args.adzuna) + int(args.company_boards is not None)
    if args.profile_check:
        if source_count or args.dashboard:
            parser.error("Use --profile-check on its own.")
        issues = check_profile(ROOT / "private" / "candidate_profile.json")
        if issues:
            print("Your private profile still needs:")
            for issue in issues:
                print(f"- {issue}")
        else:
            print("Your private candidate profile is ready for application preparation.")
        return
    if args.tailoring_check:
        if source_count or args.dashboard:
            parser.error("Use --tailoring-check on its own.")
        issues = check_tailoring_setup(ROOT)
        if issues:
            print("AI tailoring still needs:")
            for issue in issues:
                print(f"- {issue}")
        else:
            print("AI tailoring files are ready and an API key value is present. The key is verified only when you generate the first review draft.")
        return
    if args.dashboard:
        if source_count:
            parser.error("Use --dashboard on its own.")
        serve(ROOT / "data" / "applicant_zero.sqlite3", args.port)
        return
    if source_count != 1:
        parser.error("Choose exactly one source: --demo, --adzuna, --company-boards or --dashboard.")

    if args.demo:
        records = json.loads((ROOT / "data" / "demo_jobs.json").read_text(encoding="utf-8"))
        jobs = [Job(**record) for record in records]
    elif args.adzuna:
        jobs = fetch_jobs(ROOT, args.query, args.where, args.page)
    else:
        jobs, reports = fetch_company_boards_with_report(args.company_boards)
        checked = [report for report in reports if report.status == "checked"]
        unavailable = [report for report in reports if report.status == "unavailable"]
        print(f"Career boards checked: {len(checked)}. Unavailable boards skipped: {len(unavailable)}.")
        for report in unavailable:
            print(f"  - {report.company}: {report.message}")

    database = initialise_database(ROOT / "data" / "applicant_zero.sqlite3")
    if args.company_boards:
        save_board_checks(database, reports)
    queue = []
    for job in jobs:
        result = score_job(job, RISHI_PROFILE)
        save_match(database, job, result)
        queue.append((job, result))

    if args.company_boards:
        for report in reports:
            if report.status != "checked":
                continue
            active_ids = [job.external_id for job in jobs if job.company == report.company]
            mark_company_jobs_inactive(database, report.company, active_ids)

    visible_queue = queue if args.show_all else [(job, result) for job, result in queue if result.recommendation != "Skip"]
    print(f"Collected {len(queue)} roles. Showing {len(visible_queue)} roles worth reviewing; use the dashboard for the full record.")
    for job, result in sorted(visible_queue, key=lambda item: item[1].score, reverse=True):
        print(f"{result.recommendation:12} {result.score:3} | {job.title} at {job.company}")
        print(f"  Resume: {result.resume_family or 'none'}")
        for reason in result.reasons:
            print(f"  - {reason}")


if __name__ == "__main__":
    main()
