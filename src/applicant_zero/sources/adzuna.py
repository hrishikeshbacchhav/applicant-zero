import json
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from ..scoring import Job


@dataclass(frozen=True)
class QueryFetchReport:
    """Auditable result for a bounded broad-feed campaign query."""

    query: str
    location: str
    requests: int
    returned: int
    error: str = ""
    external_ids: tuple[str, ...] = ()


def load_dotenv(project_root: Path) -> None:
    """Load local credentials from runtime state or the checkout root.

    Scheduled refreshes receive the private runtime directory, while manual
    commands often receive the checkout root. Supporting both avoids a silent
    loss of the broad feed after the runtime-state migration.
    """
    roots = (project_root, Path(__file__).resolve().parents[3])
    seen: set[Path] = set()
    for root in roots:
        env_file = root / ".env"
        if env_file in seen or not env_file.exists():
            continue
        seen.add(env_file)
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


def fetch_query_plan_paged(
    project_root: Path,
    query_plan: list[tuple[str, str]],
    *,
    max_pages_per_query: int = 1,
) -> tuple[list[Job], list[QueryFetchReport]]:
    """Fetch a small campaign slice, paging only when a page is full.

    Adzuna returns up to fifty listings per request. A full first page is the
    useful signal that a second page may contain distinct roles; sparse pages
    do not spend another request. The caller owns the overall daily request
    budget, so this function has no hidden retries or unbounded pagination.
    """
    pages = max(1, min(int(max_pages_per_query), 2))
    jobs_by_id: dict[str, Job] = {}
    reports: list[QueryFetchReport] = []
    for query, where in query_plan:
        request_count = returned = 0
        query_ids: set[str] = set()
        error = ""
        for page in range(1, pages + 1):
            try:
                result = fetch_jobs(project_root, query, where, page)
                request_count += 1
                returned += len(result)
                for job in result:
                    jobs_by_id[job.external_id] = job
                    query_ids.add(job.external_id)
            except (OSError, RuntimeError, ValueError) as caught:
                request_count += 1
                error = str(caught)
                break
            if len(result) < 50:
                break
        reports.append(QueryFetchReport(
            query, where, request_count, returned, error,
            tuple(sorted(query_ids)),
        ))
    return list(jobs_by_id.values()), reports
