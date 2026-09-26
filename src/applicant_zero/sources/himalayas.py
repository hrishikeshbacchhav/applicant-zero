"""Read a bounded, attributed slice of Himalayas' public remote-jobs API."""

from dataclasses import dataclass
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..scoring import Job
from .metadata import append_listing_metadata


@dataclass(frozen=True)
class HimalayasReport:
    requests: int


def build_jobs_url(*, cursor: str = "", limit: int = 20) -> str:
    """Build one documented browse request without constructing a cursor."""
    params = {"limit": max(1, min(20, int(limit)))}
    if cursor:
        params["cursor"] = cursor
    return "https://himalayas.app/jobs/api?" + urlencode(params)


def _text_list(value: object) -> str:
    if isinstance(value, list):
        return ", ".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "").strip()


def _salary(result: dict) -> str:
    minimum, maximum = result.get("minSalary"), result.get("maxSalary")
    if minimum in (None, "") and maximum in (None, ""):
        return ""
    currency = str(result.get("currency") or "").strip()
    period = str(result.get("salaryPeriod") or "annual").strip()
    values = [str(value) for value in (minimum, maximum) if value not in (None, "")]
    return f"{'–'.join(values)} {currency} per {period}".strip()


def _job_from_result(result: dict) -> Job:
    identifier = str(result.get("guid") or result.get("id") or result.get("applicationLink") or result.get("title") or "unknown")
    restrictions = _text_list(result.get("locationRestrictions")) or "eligibility not supplied"
    description = str(result.get("description") or result.get("excerpt") or "")
    categories = _text_list(result.get("category"))
    if categories:
        description = f"{description}\nCategories: {categories}".strip()
    application_link = str(result.get("applicationLink") or "").strip()
    if application_link:
        description = f"{description}\nApplication link: {application_link}".strip()
    return Job(
        external_id=f"himalayas:{identifier}",
        title=str(result.get("title") or "Untitled role"),
        company=str(result.get("companyName") or "Unknown company"),
        location=f"Remote, {restrictions}",
        source="Himalayas",
        # Himalayas' public API asks applications to credit and link back to
        # Himalayas. The job's direct application URL remains in the listing
        # detail above for the candidate to verify and use personally.
        url="https://himalayas.app/jobs",
        description=append_listing_metadata(
            description,
            posted_at=result.get("pubDate", ""),
            employment_type=result.get("employmentType", ""),
            salary=_salary(result),
        ),
        seniority=_text_list(result.get("seniority")) or "graduate",
    )


def fetch_jobs_with_report(*, max_pages: int = 5, page_size: int = 20) -> tuple[list[Job], HimalayasReport]:
    """Read at most five API pages, following only cursors returned by API."""
    cursor = ""
    jobs: list[Job] = []
    requests = 0
    for _ in range(max(1, min(5, int(max_pages)))):
        request = Request(
            build_jobs_url(cursor=cursor, limit=page_size),
            headers={"Accept": "application/json", "User-Agent": "Applicant-Zero/0.1 (private job discovery)"},
        )
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        requests += 1
        rows = payload.get("jobs", []) if isinstance(payload, dict) else []
        jobs.extend(_job_from_result(row) for row in rows if isinstance(row, dict))
        cursor = str(payload.get("nextCursor") or "") if isinstance(payload, dict) else ""
        if not cursor:
            break
    return jobs, HimalayasReport(requests=requests)


def fetch_jobs(*, max_pages: int = 5, page_size: int = 20) -> list[Job]:
    """Convenience reader for a capped public API slice."""
    jobs, _ = fetch_jobs_with_report(max_pages=max_pages, page_size=page_size)
    return jobs
