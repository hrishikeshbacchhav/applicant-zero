"""Read Jobicy's public remote-jobs feed as a bounded APAC supplement."""

import json
from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..scoring import Job
from .metadata import append_listing_metadata


TARGET_INDUSTRIES = ("data-science", "engineering", "supporting", "management")


@dataclass(frozen=True)
class TargetedFetchReport:
    """Summary of the bounded public Jobicy category refresh."""

    requests: int
    errors: tuple[str, ...]


def build_jobs_url(*, count: int = 200, geo: str = "apac", industry: str = "") -> str:
    """Build one public, attributed Jobicy request with a hard result cap."""
    params = {"count": max(1, min(200, int(count))), "geo": geo.strip().lower()}
    if industry.strip():
        params["industry"] = industry.strip().lower()
    return "https://jobicy.com/api/v2/remote-jobs?" + urlencode(params)


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


def fetch_jobs(*, count: int = 200, geo: str = "apac", industry: str = "") -> list[Job]:
    """Read one ordinary public APAC feed page; no key or session is used."""
    request = Request(
        build_jobs_url(count=count, geo=geo, industry=industry),
        headers={"Accept": "application/json", "User-Agent": "Applicant-Zero/0.1 (private job discovery)"},
    )
    with urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    rows = payload.get("jobs", []) if isinstance(payload, dict) else []
    return [_job_from_result(row) for row in rows if isinstance(row, dict)]


def fetch_targeted_jobs(
    *, count: int = 100, geo: str = "apac", industries: tuple[str, ...] = TARGET_INDUSTRIES
) -> tuple[list[Job], TargetedFetchReport]:
    """Read a small role-focused APAC slice from documented Jobicy categories.

    The public API publishes only the most recent seven days. Querying the
    supplied category endpoints makes the limited refresh useful for data, IT
    support, technical and operations-oriented roles instead of relying on one
    general page to happen to contain them. Each request remains attributed,
    unauthenticated and bounded; an unavailable category never stops the
    remaining source refresh.
    """
    jobs: list[Job] = []
    errors: list[str] = []
    requests = 0
    for industry in industries:
        try:
            jobs.extend(fetch_jobs(count=count, geo=geo, industry=industry))
            requests += 1
        except (OSError, ValueError, json.JSONDecodeError) as error:
            requests += 1
            errors.append(f"{industry}: {error}")
    return jobs, TargetedFetchReport(requests=requests, errors=tuple(errors))
