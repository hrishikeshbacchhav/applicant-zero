import argparse
import json
from pathlib import Path

from .profile import RISHI_PROFILE
from .scoring import Job, score_job
from .storage import initialise_database, save_match
from .sources.adzuna import fetch_jobs
from .sources.company_boards import fetch_company_boards


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank job listings for Applicant Zero.")
    parser.add_argument("--demo", action="store_true", help="Import the safe demo job feed.")
    parser.add_argument("--adzuna", action="store_true", help="Search Adzuna's official Australian job API.")
    parser.add_argument("--company-boards", type=Path, help="Read public Greenhouse and Lever boards listed in a JSON file.")
    parser.add_argument("--query", default="data analyst", help="Job title or skill query for Adzuna.")
    parser.add_argument("--where", default="Sydney", help="Location query for Adzuna.")
    parser.add_argument("--page", type=int, default=1, help="Adzuna results page.")
    args = parser.parse_args()
    source_count = int(args.demo) + int(args.adzuna) + int(args.company_boards is not None)
    if source_count != 1:
        parser.error("Choose exactly one source: --demo, --adzuna or --company-boards.")

    if args.demo:
        records = json.loads((ROOT / "data" / "demo_jobs.json").read_text(encoding="utf-8"))
        jobs = [Job(**record) for record in records]
    elif args.adzuna:
        jobs = fetch_jobs(ROOT, args.query, args.where, args.page)
    else:
        jobs = fetch_company_boards(args.company_boards)

    database = initialise_database(ROOT / "data" / "applicant_zero.sqlite3")
    queue = []
    for job in jobs:
        result = score_job(job, RISHI_PROFILE)
        save_match(database, job, result)
        queue.append((job, result))

    for job, result in sorted(queue, key=lambda item: item[1].score, reverse=True):
        print(f"{result.recommendation:12} {result.score:3} | {job.title} at {job.company}")
        print(f"  Resume: {result.resume_family or 'none'}")
        for reason in result.reasons:
            print(f"  - {reason}")


if __name__ == "__main__":
    main()
