import argparse
import json
from pathlib import Path

from .profile import RISHI_PROFILE
from .scoring import Job, score_job
from .storage import initialise_database, save_match


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank a safe demo feed of jobs for Applicant Zero.")
    parser.add_argument("--demo", action="store_true", help="Import the safe demo job feed.")
    args = parser.parse_args()
    if not args.demo:
        parser.error("Use --demo for the first local prototype run.")

    records = json.loads((ROOT / "data" / "demo_jobs.json").read_text(encoding="utf-8"))
    database = initialise_database(ROOT / "data" / "applicant_zero.sqlite3")
    queue = []
    for record in records:
        job = Job(**record)
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
