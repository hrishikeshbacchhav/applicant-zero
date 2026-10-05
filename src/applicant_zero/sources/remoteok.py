"""Read Remote OK's public, attributed JSON jobs feed."""

import json
from urllib.request import Request, urlopen

from ..scoring import Job
from .metadata import append_listing_metadata


API_URL = "https://remoteok.com/api"


def _text_list(value: object) -> str:
    if isinstance(value, list):
        return ", ".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "").strip()


def _salary(result: dict) -> str:
    minimum, maximum = result.get("salary_min"), result.get("salary_max")
    values = [str(value) for value in (minimum, maximum) if value not in (None, "")]
    if not values:
        return ""
    return "–".join(values) + (" USD" if result.get("salary_currency") in (None, "", "USD") else f" {result['salary_currency']}")


def _job_from_result(result: dict) -> Job | None:
    """Map a feed listing while skipping Remote OK's leading legal record."""
    title = str(result.get("position") or result.get("title") or "").strip()
    identifier = str(result.get("id") or result.get("slug") or "").strip()
    if not title or not identifier:
        return None
    location = _text_list(result.get("location") or result.get("location_restrictions") or result.get("geo"))
    description = str(result.get("description") or "")
    tags = _text_list(result.get("tags"))
    if tags:
        description = f"{description}\nTags: {tags}".strip()
    url = str(result.get("url") or "").strip()
    slug = str(result.get("slug") or "").strip()
    if not url and slug:
        url = f"https://remoteok.com/remote-jobs/{slug}"
    return Job(
        external_id=f"remoteok:{identifier}",
        title=title,
        company=str(result.get("company") or result.get("company_name") or "Unknown company"),
        location=f"Remote, {location or 'eligibility not supplied'}",
        source="Remote OK",
        # Remote OK asks users of the feed to credit it and link back to the
        # canonical listing. The queue opens this supplied or canonical URL.
        url=url or API_URL,
        description=append_listing_metadata(
            description,
            posted_at=result.get("date") or result.get("epoch") or "",
            salary=_salary(result),
        ),
    )


def fetch_jobs(*, max_items: int = 250) -> list[Job]:
    """Read one public feed document with a conservative local result cap."""
    request = Request(
        API_URL,
        headers={"Accept": "application/json", "User-Agent": "Applicant-Zero/0.1 (private job discovery)"},
    )
    with urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    rows = payload if isinstance(payload, list) else []
    jobs = [_job_from_result(row) for row in rows if isinstance(row, dict)]
    return [job for job in jobs if job is not None][:max(1, min(250, int(max_items)))]
