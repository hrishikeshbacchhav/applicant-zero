"""Read Jobicy's public remote-jobs feed as a bounded APAC supplement."""

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..scoring import Job
from .metadata import append_listing_metadata


def build_jobs_url(*, count: int = 200, geo: str = "apac") -> str:
    """Build one public, attributed Jobicy request with a hard result cap."""
    return "https://jobicy.com/api/v2/remote-jobs?" + urlencode({
        "count": max(1, min(200, int(count))), "geo": geo.strip().lower(),
    })


def _job_from_result(result: dict) -> Job:
    identifier = str(result.get("id") or result.get("url") or result.get("jobTitle") or "unknown")
    job_type = result.get("jobType", [])
    employment_type = ", ".join(str(item) for item in job_type) if isinstance(job_type, list) else str(job_type or "")
    industries = result.get("jobIndustry", [])
    industry_text = ", ".join(str(item) for item in industries) if isinstance(industries, list) else str(industries or "")
    description = str(result.get("jobDescription") or result.get("jobExcerpt") or "")
    if industry_text:
        description = f"{description}\nCategories: {industry_text}".strip()
    return Job(
        external_id=f"jobicy:{identifier}",
        title=str(result.get("jobTitle") or "Untitled role"),
        company=str(result.get("companyName") or "Unknown company"),
        location=f"Remote, {str(result.get('jobGeo') or 'eligibility not supplied')}",
        source="Jobicy",
        # The free public endpoint deliberately returns Jobicy's canonical
        # listing URL. Preserve that attribution rather than guessing an ATS
        # application destination.
        url=str(result.get("url") or ""),
        description=append_listing_metadata(
            description, posted_at=result.get("pubDate", result.get("datePosted", "")),
            employment_type=employment_type,
        ),
        seniority=str(result.get("jobLevel") or "graduate"),
    )


def fetch_jobs(*, count: int = 200, geo: str = "apac") -> list[Job]:
    """Read one ordinary public APAC feed page; no key or session is used."""
    request = Request(
        build_jobs_url(count=count, geo=geo),
        headers={"Accept": "application/json", "User-Agent": "Applicant-Zero/0.1 (private job discovery)"},
    )
    with urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    rows = payload.get("jobs", []) if isinstance(payload, dict) else []
    return [_job_from_result(row) for row in rows if isinstance(row, dict)]
