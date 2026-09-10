import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from ..scoring import Job


def load_dotenv(project_root: Path) -> None:
    """Load a local .env file without adding a third-party dependency."""
    env_file = project_root / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def build_search_url(app_id: str, app_key: str, query: str, where: str, page: int = 1) -> str:
    parameters = urlencode({
        "app_id": app_id,
        "app_key": app_key,
        "what": query,
        "where": where,
        "results_per_page": 50,
        "content-type": "application/json",
    })
    return f"https://api.adzuna.com/v1/api/jobs/au/search/{page}?{parameters}"


def _job_from_result(result: dict) -> Job:
    company = result.get("company", {}).get("display_name", "Unknown company")
    location = result.get("location", {}).get("display_name", "Unknown location")
    return Job(
        external_id=f"adzuna:{result['id']}",
        title=result.get("title", "Untitled role"),
        company=company,
        location=location,
        source="Adzuna",
        url=result.get("redirect_url", ""),
        description=result.get("description", ""),
    )


def fetch_jobs(project_root: Path, query: str, where: str, page: int = 1) -> list[Job]:
    load_dotenv(project_root)
    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        raise RuntimeError("Missing Adzuna credentials. Create a local .env file from .env.example.")

    url = build_search_url(app_id, app_key, query, where, page)
    with urlopen(url, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return [_job_from_result(result) for result in payload.get("results", [])]


def fetch_query_batch(
    project_root: Path, queries: list[str], where: str = "Sydney", max_queries: int | None = None
) -> tuple[list[Job], list[str]]:
    """Run a small, controlled set of search queries and collapse repeated listings."""
    selected = [query.strip() for query in queries if query.strip()]
    if max_queries is not None:
        selected = selected[:max_queries]
    jobs_by_id: dict[str, Job] = {}
    errors: list[str] = []
    for query in selected:
        try:
            for job in fetch_jobs(project_root, query, where):
                jobs_by_id[job.external_id] = job
        except (OSError, RuntimeError, ValueError) as error:
            errors.append(f"{query}: {error}")
    return list(jobs_by_id.values()), errors


def fetch_query_plan(
    project_root: Path, query_plan: list[tuple[str, str]], max_queries: int | None = None
) -> tuple[list[Job], list[str]]:
    """Run an ordered multi-location campaign plan without duplicating jobs."""
    selected = query_plan if max_queries is None else query_plan[:max(0, max_queries)]
    jobs_by_id: dict[str, Job] = {}
    errors: list[str] = []
    for query, where in selected:
        try:
            for job in fetch_jobs(project_root, query, where):
                jobs_by_id[job.external_id] = job
        except (OSError, RuntimeError, ValueError) as error:
            errors.append(f"{query} ({where}): {error}")
    return list(jobs_by_id.values()), errors
