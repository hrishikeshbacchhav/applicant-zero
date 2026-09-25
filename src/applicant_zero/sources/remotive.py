"""Read Remotive's public remote-job feed as an attributed supplement."""

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..scoring import Job
from .metadata import append_listing_metadata


def build_jobs_url(*, count: int = 200) -> str:
    """Build one bounded request to Remotive's documented public endpoint."""
    return "https://remotive.com/api/remote-jobs?" + urlencode({"limit": max(1, min(200, int(count)))})


def _job_from_result(result: dict) -> Job:
    identifier = str(result.get("id") or result.get("url") or result.get("title") or "unknown")
    location = str(result.get("candidate_required_location") or "eligibility not supplied")
    description = str(result.get("description") or "")
    category = str(result.get("category") or "").strip()
    if category:
        description = f"{description}\nCategory: {category}".strip()
    return Job(
        external_id=f"remotive:{identifier}",
        title=str(result.get("title") or "Untitled role"),
        company=str(result.get("company_name") or "Unknown company"),
        location=f"Remote, {location}",
        source="Remotive",
        # Remotive's terms require its listing URL and source attribution to
        # be preserved. The dashboard therefore opens this URL directly.
        url=str(result.get("url") or ""),
        description=append_listing_metadata(
            description,
            posted_at=result.get("publication_date", ""),
            employment_type=result.get("job_type", ""),
            salary=result.get("salary", ""),
        ),
    )


def fetch_jobs(*, count: int = 200) -> list[Job]:
    """Read one ordinary public feed page without a key, account or session."""
    request = Request(
        build_jobs_url(count=count),
        headers={"Accept": "application/json", "User-Agent": "Applicant-Zero/0.1 (private job discovery)"},
    )
    with urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    rows = payload.get("jobs", []) if isinstance(payload, dict) else []
    return [_job_from_result(row) for row in rows if isinstance(row, dict)]
