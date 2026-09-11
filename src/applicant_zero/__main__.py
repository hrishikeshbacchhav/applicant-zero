import argparse
import json
import sqlite3
from pathlib import Path

from .ai_drafting import check_tailoring_setup
from .daily_digest import create_daily_digest
from .dashboard import serve
from .private_profile import check_profile
from .private_profile import load_profile
from .application_answers import ensure_answer_library
from .candidate_facts import ensure_fact_library
from .profile import RISHI_PROFILE
from .scoring import Job, score_job
from .sources.adzuna import fetch_jobs, fetch_query_plan, fetch_query_plan_paged
from .campaigns import active_lanes, consume_discovery_query_plan, discovery_query_status, max_pages_per_query, next_discovery_query_plan
from .sources.company_boards import fetch_company_boards_with_report
from .discovery_measurements import measure_sources
from .storage import (
    deactivate_stale_broad_feed_jobs,
    initialise_database,
    mark_company_jobs_inactive,
    prune_inactive_discovery_records,
    record_refresh_run,
    record_source_measurements,
    save_discovery_inventory,
    save_board_checks,
    save_match,
)
from .system_health import health_report
from .runtime import backup_database, database_path, prepare_state, recover_database, synchronise_board_registry
from .resume_evidence import ResumeEvidenceError, create_resume_evidence_inventory
from .gmail_sync import GmailSetupError, connect_gmail, sync_gmail
from .provider_trials import ProviderTrialError, assess_trial_sample, load_trial_sample
from .sources.jobdatalake import run_trial as run_jobdatalake_trial
from .licensed_providers import enabled_licensed_providers, provider_remaining_today, record_provider_requests

ROOT = Path(__file__).resolve().parents[2]


def _sync_private_facts(state: Path) -> None:
    profile = load_profile(state / "private" / "candidate_profile.json")
    if profile:
        ensure_fact_library(state, profile, ensure_answer_library(state, profile))


def _save_jobs(
    database,
    jobs: list[Job],
    show_all: bool = False,
    enabled_lanes: set[str] | None = None,
    persist_skips: bool = True,
) -> list[tuple[Job, object]]:
    queue = []
    for job in jobs:
        result = score_job(job, RISHI_PROFILE, enabled_lanes)
        if persist_skips or result.recommendation != "Skip":
            save_match(database, job, result)
        queue.append((job, result))
    return queue if show_all else [(job, result) for job, result in queue if result.recommendation != "Skip"]


def _board_path(state: Path) -> Path:
    return synchronise_board_registry(ROOT)


def run_daily_refresh(state: Path, max_queries: int | None = None) -> tuple[int, int, str]:
    """Refresh public boards and a capped query batch as one daily run."""
    board_jobs, reports = fetch_company_boards_with_report(_board_path(state))
    query_status = discovery_query_status(state, max_queries)
    query_plan = next_discovery_query_plan(state, max_queries)
    query_jobs, query_reports = fetch_query_plan_paged(
        state, query_plan, max_pages_per_query=max_pages_per_query(state)
    )
    request_count = sum(report.requests for report in query_reports)
    query_errors = [report for report in query_reports if report.error]
    consume_discovery_query_plan(state, len(query_plan), request_count)
    licensed_jobs: list[Job] = []
    licensed_requests: dict[str, int] = {}
    licensed_failures: dict[str, int] = {}
    provider_notes: list[str] = []
    unique_queries = list(dict.fromkeys(query for query, _ in query_plan))
    for provider in enabled_licensed_providers(state):
        allowance = min(provider.max_requests_per_refresh, provider_remaining_today(state, provider))
        if allowance <= 0:
            provider_notes.append(f"{provider.label} daily allowance exhausted")
            continue
        if provider.identifier != "jobdatalake":
            provider_notes.append(f"{provider.label} has no adapter installed")
            continue
        provider_jobs, provider_reports = run_jobdatalake_trial(state, unique_queries, max_requests=allowance)
        used = sum(report.requests for report in provider_reports)
        record_provider_requests(state, provider, used)
        licensed_jobs.extend(provider_jobs)
        licensed_requests[provider.label] = used
        failures = sum(bool(report.error) for report in provider_reports)
        licensed_failures[provider.label] = failures
        provider_notes.append(f"{provider.label} used {used} licensed request(s), {len(provider_jobs)} role(s) returned")
    jobs = list({job.external_id: job for job in [*board_jobs, *query_jobs, *licensed_jobs]}.values())
    database = initialise_database(database_path(ROOT))
    save_discovery_inventory(database, jobs)
    save_board_checks(database, reports)
    visible = _save_jobs(database, jobs, enabled_lanes=active_lanes(state), persist_skips=False)
    for report in reports:
        if report.status == "checked":
            mark_company_jobs_inactive(database, report.company, [job.external_id for job in board_jobs if job.company == report.company])
    checked = sum(report.status == "checked" for report in reports)
    unavailable = sum(report.status == "unavailable" for report in reports)
    stale_broad = deactivate_stale_broad_feed_jobs(database)
    pruned = prune_inactive_discovery_records(database)
    skipped = len(jobs) - len(visible)
    detail = f"{checked} company boards checked; {len(query_plan)} campaign search queries used {request_count} broad-feed API call(s); {query_status['remaining_today']} broad-feed calls remained before this run; {skipped} hard skips not stored"
    if stale_broad:
        detail += f"; {stale_broad} old broad-feed listing(s) marked inactive"
    if pruned:
        detail += f"; {pruned} old inactive discovery record(s) removed"
    if query_errors:
        detail += f"; {len(query_errors)} query source issue(s) skipped"
    if provider_notes:
        detail += "; " + "; ".join(provider_notes)
    request_counts = {"Adzuna": request_count}
    failure_counts = {"Adzuna": len(query_errors)}
    request_counts.update(licensed_requests)
    failure_counts.update(licensed_failures)
    for report in reports:
        source = getattr(report, "ats", "") or "Public board"
        request_counts[source] = request_counts.get(source, 0) + 1
        if report.status == "unavailable":
            failure_counts[source] = failure_counts.get(source, 0) + 1
    record_source_measurements(
        database,
        measure_sources(
            jobs, {job.external_id for job, _ in visible},
            request_counts=request_counts, failure_counts=failure_counts,
        ),
    )
    record_refresh_run(database, "Daily discovery refresh", len(jobs), len(visible), checked, unavailable, detail)
    return len(jobs), len(visible), detail


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank job listings for Applicant Zero.")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--adzuna", action="store_true")
    parser.add_argument("--company-boards", type=Path)
    parser.add_argument("--daily-refresh", action="store_true")
    parser.add_argument("--daily-digest", action="store_true")
    parser.add_argument("--health-check", action="store_true")
    parser.add_argument("--backup", action="store_true")
    parser.add_argument("--max-queries", type=int)
    parser.add_argument("--query", default="data analyst")
    parser.add_argument("--where", default="Sydney")
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--dashboard", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--show-all", action="store_true")
    parser.add_argument("--profile-check", action="store_true")
    parser.add_argument("--tailoring-check", action="store_true")
    parser.add_argument("--resume-inventory", action="store_true")
    parser.add_argument("--gmail-connect", action="store_true")
    parser.add_argument("--gmail-sync", action="store_true")
    parser.add_argument("--gmail-days", type=int, default=2)
    parser.add_argument("--provider-trial-report", type=Path)
    parser.add_argument("--jobdatalake-trial", action="store_true")
    parser.add_argument("--max-provider-requests", type=int, default=5)
    args = parser.parse_args()
    state = prepare_state(ROOT)
    database = database_path(ROOT)
    recovery_message = recover_database(ROOT)
    if recovery_message:
        print(recovery_message)
    source_count = int(args.demo) + int(args.adzuna) + int(args.company_boards is not None) + int(args.daily_refresh) + int(args.daily_digest) + int(args.health_check) + int(args.backup) + int(args.gmail_connect) + int(args.gmail_sync) + int(args.provider_trial_report is not None) + int(args.jobdatalake_trial)
    if args.provider_trial_report:
        if source_count != 1 or args.dashboard:
            parser.error("Use --provider-trial-report on its own.")
        try:
            jobs = load_trial_sample(args.provider_trial_report, args.provider_trial_report.stem)
            database_connection = initialise_database(database)
            from .storage import list_matches
            report = assess_trial_sample(jobs, list_matches(database_connection, include_duplicates=True))
            print("Provider trial sample (local only): " + "; ".join(f"{key.replace('_', ' ')} {value}" for key, value in report.items()))
        except (ProviderTrialError, OSError, sqlite3.Error) as error:
            print(f"Provider trial sample could not be assessed: {error}")
        return
    if args.jobdatalake_trial:
        if source_count != 1 or args.dashboard:
            parser.error("Use --jobdatalake-trial on its own.")
        try:
            from .storage import list_inventory_records
            queries = []
            for query, _ in discovery_query_status(state, args.max_provider_requests)["planned"]:
                if query not in queries:
                    queries.append(query)
            jobs, reports = run_jobdatalake_trial(state, queries, max_requests=args.max_provider_requests)
            database_connection = initialise_database(database)
            report = assess_trial_sample(jobs, list_inventory_records(database_connection))
            failures = sum(bool(item.error) for item in reports)
            print("JobDataLake trial (no listings saved): " + "; ".join(f"{key.replace('_', ' ')} {value}" for key, value in report.items()) + f"; requests {sum(item.requests for item in reports)}; issues {failures}")
        except (OSError, RuntimeError, ValueError, sqlite3.Error) as error:
            print(f"JobDataLake trial could not run: {error}")
        return
    _sync_private_facts(state)
    if args.gmail_connect:
        if source_count != 1 or args.dashboard:
            parser.error("Use --gmail-connect on its own.")
        try:
            print(connect_gmail(state))
        except GmailSetupError as error:
            print(f"Gmail connection was not created: {error}")
        return
    if args.gmail_sync:
        if source_count != 1 or args.dashboard:
            parser.error("Use --gmail-sync on its own.")
        try:
            result = sync_gmail(state, database, args.gmail_days)
            print(f"Gmail sync complete: {result['fetched']} new message(s) recorded; {result['matched']} matched; {result['updated']} tracker update(s).")
        except GmailSetupError as error:
            print(f"Gmail sync did not run: {error}")
        return
    if args.resume_inventory:
        if source_count or args.dashboard: parser.error("Use --resume-inventory on its own.")
        try:
            print(f"Private résumé evidence inventory created: {create_resume_evidence_inventory(state)}")
        except ResumeEvidenceError as error:
            print(f"Could not create private résumé evidence inventory: {error}")
        return
    if args.profile_check:
        if source_count or args.dashboard: parser.error("Use --profile-check on its own.")
        issues = check_profile(state / "private" / "candidate_profile.json")
        print("Your private profile still needs:" if issues else "Your private candidate profile is ready for application preparation.")
        for issue in issues: print(f"- {issue}")
        return
    if args.tailoring_check:
        if source_count or args.dashboard: parser.error("Use --tailoring-check on its own.")
        issues = check_tailoring_setup(state)
        print("AI tailoring still needs:" if issues else "AI tailoring files are ready and an API key value is present. The key is verified only when you generate the first review draft.")
        for issue in issues: print(f"- {issue}")
        return
    if args.dashboard:
        if source_count: parser.error("Use --dashboard on its own.")
        backup_database(ROOT, "dashboard")
        serve(database, args.port)
        return
    if args.daily_digest:
        if source_count != 1: parser.error("Use --daily-digest on its own.")
        print(f"Daily priority digest created: {create_daily_digest(database)}")
        return
    if args.health_check:
        if source_count != 1: parser.error("Use --health-check on its own.")
        for label, healthy, detail in health_report(state):
            print(f"{'OK' if healthy else 'CHECK'} · {label}: {detail}")
        return
    if args.backup:
        if source_count != 1: parser.error("Use --backup on its own.")
        backup = backup_database(ROOT, "manual")
        print(f"Private database snapshot created: {backup}" if backup else "No database snapshot was needed yet.")
        return
    if args.daily_refresh:
        if source_count != 1: parser.error("Use --daily-refresh on its own.")
        backup_database(ROOT, "refresh")
        collected, relevant, detail = run_daily_refresh(state, args.max_queries)
        print(f"Daily refresh complete: {collected} roles collected; {relevant} worth reviewing. {detail}.")
        return
    if source_count != 1: parser.error("Choose exactly one source: --demo, --adzuna, --company-boards, --daily-refresh, --daily-digest or --dashboard.")
    reports = []
    if args.demo:
        jobs = [Job(**record) for record in json.loads((ROOT / "data" / "demo_jobs.json").read_text(encoding="utf-8"))]
    elif args.adzuna:
        jobs = fetch_jobs(state, args.query, args.where, args.page)
    else:
        jobs, reports = fetch_company_boards_with_report(args.company_boards)
        print(f"Career boards checked: {sum(report.status == 'checked' for report in reports)}. Unavailable boards skipped: {sum(report.status == 'unavailable' for report in reports)}.")
    backup_database(ROOT, "collection")
    database = initialise_database(database)
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
