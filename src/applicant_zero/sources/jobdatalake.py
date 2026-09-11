"""Optional adapter for a licensed JobDataLake discovery trial."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..scoring import Job
from .adzuna import load_dotenv


@dataclass(frozen=True)
class LicensedFetchReport:
    query: str
    requests: int
    returned: int
    error: str = ""


def build_search_url(api_key: str, query: str, *, page: int = 1, location: str = "Sydney", country: str = "AU") -> str:
    """Build a documented, bounded search request without exposing the key."""
    parameters = urlencode({
        "q": query, "page": max(1, page), "per_page": 100,
        "countries": country, "location": location, "employment_type": "full_time",
        "sort_by": "posted_at:desc",
    })
    return f"https://api.jobdatalake.com/v1/jobs?{parameters}"


def _job_from_result(result: dict) -> Job:
    handle = str(result.get("job_handle") or result.get("id") or result.get("url") or result.get("title", "unknown"))
    locations = result.get("locations", [])
    location = ", ".join(str(value) for value in locations if str(value).strip()) if isinstance(locations, list) else str(locations or "Unknown location")
    skills = result.get("required_skills", [])
    skill_text = ", ".join(str(value) for value in skills) if isinstance(skills, list) else ""
    description = str(result.get("description") or result.get("requirements") or "")
    if skill_text:
        description = f"{description}\nRequired skills: {skill_text}".strip()
    company_value = result.get("company", {})
    company = company_value.get("name", "") if isinstance(company_value, dict) else str(company_value or "")
    return Job(
        external_id=f"jobdatalake:{handle}",
        title=str(result.get("title") or "Untitled role"),
        company=str(result.get("company_name") or company or "Unknown company"),
        location=location,
        source="JobDataLake",
        url=str(result.get("url") or result.get("apply_url") or ""),
        description=description,
    )


def fetch_jobs(project_root: Path, query: str, *, page: int = 1, location: str = "Sydney") -> list[Job]:
    load_dotenv(project_root)
    api_key = os.getenv("JOBDATALAKE_API_KEY")
    if not api_key:
        raise RuntimeError("Missing JOBDATALAKE_API_KEY. Add it locally to .env before running a provider trial.")
    request = Request(
        build_search_url(api_key, query, page=page, location=location),
        headers={"X-API-Key": api_key, "Accept": "application/json", "User-Agent": "Applicant-Zero/0.1 (private job discovery)"},
    )
    with urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    rows = payload.get("jobs", []) if isinstance(payload, dict) else []
    return [_job_from_result(row) for row in rows if isinstance(row, dict)]


def run_trial(project_root: Path, queries: list[str], *, max_requests: int = 5) -> tuple[list[Job], list[LicensedFetchReport]]:
    """Run a small no-retry provider evaluation, never an unbounded backfill."""
    jobs_by_id: dict[str, Job] = {}
    reports: list[LicensedFetchReport] = []
    for query in [value.strip() for value in queries if value.strip()][:max(0, min(max_requests, 20))]:
        try:
            jobs = fetch_jobs(project_root, query)
        except (OSError, RuntimeError, ValueError) as error:
            reports.append(LicensedFetchReport(query, 1, 0, str(error)))
            continue
        for job in jobs:
            jobs_by_id[job.external_id] = job
        reports.append(LicensedFetchReport(query, 1, len(jobs)))
    return list(jobs_by_id.values()), reports
