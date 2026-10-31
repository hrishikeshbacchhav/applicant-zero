"""Read a small, registered The Muse API slice when locally configured.

The Muse publishes a documented jobs API, but requires application
registration for use beyond testing.  This adapter is therefore deliberately
disabled until the candidate supplies their own local API key.  It never
scrapes the website and preserves the provider's landing-page attribution.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..scoring import Job
from .adzuna import load_dotenv
from .metadata import append_listing_metadata


API_URL = "https://www.themuse.com/api/public/jobs"
TARGET_CATEGORIES = ("Data and Analytics", "Business Operations", "Computer and IT", "Administration and Office")


@dataclass(frozen=True)
class TheMuseReport:
    requests: int
    errors: tuple[str, ...] = ()


def configured(project_root: Path) -> bool:
    """Return whether a locally registered key is available, without exposing it."""
    load_dotenv(project_root)
    return bool(os.getenv("THEMUSE_API_KEY", "").strip())


def build_jobs_url(api_key: str, *, category: str, location: str = "Australia", page: int = 0) -> str:
    """Build a documented, one-page category/location API request."""
    return API_URL + "?" + urlencode({
        "api_key": api_key,
        "page": max(0, int(page)),
        "category": category.strip(),
        "location": location.strip(),
        "descending": "true",
    })


def _names(value: object) -> str:
    if isinstance(value, list):
        return ", ".join(
            str(item.get("name") if isinstance(item, dict) else item).strip()
            for item in value if str(item.get("name") if isinstance(item, dict) else item).strip()
        )
    return str(value or "").strip()


def _job_from_result(result: dict) -> Job:
    identifier = str(result.get("id") or result.get("refs", {}).get("landing_page") or result.get("name") or "unknown")
    company = result.get("company", {})
    company_name = str(company.get("name") if isinstance(company, dict) else company or "Unknown company")
    refs = result.get("refs", {})
    url = str(refs.get("landing_page") if isinstance(refs, dict) else "")
    categories = _names(result.get("categories"))
    description = str(result.get("contents") or result.get("description") or "")
    if categories:
        description = f"{description}\nCategories: {categories}".strip()
    return Job(
        external_id=f"themuse:{identifier}",
        title=str(result.get("name") or "Untitled role"),
        company=company_name,
        location=_names(result.get("locations")) or "Australia",
        source="The Muse",
        url=url or API_URL,
        description=append_listing_metadata(
            description,
            posted_at=result.get("publication_date", ""),
            employment_type=result.get("type", ""),
        ),
        seniority=_names(result.get("levels")),
    )


def fetch_targeted_jobs(
    project_root: Path, *, categories: tuple[str, ...] = TARGET_CATEGORIES, location: str = "Australia", max_requests: int = 4
) -> tuple[list[Job], TheMuseReport]:
    """Fetch at most four registered, Australia-filtered category pages."""
    load_dotenv(project_root)
    api_key = os.getenv("THEMUSE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing THEMUSE_API_KEY. Register the local app with The Muse before enabling this source.")
    selected = tuple(category for category in categories if category.strip())[:max(1, min(4, int(max_requests)))]
    jobs: list[Job] = []
    errors: list[str] = []
    for category in selected:
        try:
            request = Request(
                build_jobs_url(api_key, category=category, location=location),
                headers={"Accept": "application/json", "User-Agent": "Applicant-Zero/0.1 (private job discovery)"},
            )
            with urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
            rows = payload.get("results", []) if isinstance(payload, dict) else []
            jobs.extend(_job_from_result(row) for row in rows if isinstance(row, dict))
        except (OSError, ValueError, json.JSONDecodeError) as error:
            errors.append(f"{category}: {error}")
    return jobs, TheMuseReport(requests=len(selected), errors=tuple(errors))
