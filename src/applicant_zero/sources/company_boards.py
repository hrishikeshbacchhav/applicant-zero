import json
from pathlib import Path
from urllib.request import urlopen

from ..scoring import Job


def _get_json(url: str) -> dict | list:
    with urlopen(url, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _greenhouse_jobs(company: str, token: str) -> list[Job]:
    payload = _get_json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true")
    return [
        Job(
            external_id=f"greenhouse:{token}:{item['id']}",
            title=item.get("title", "Untitled role"),
            company=company,
            location=item.get("location", {}).get("name", "Unknown location"),
            source="Greenhouse",
            url=item.get("absolute_url", ""),
            description=item.get("content", ""),
        )
        for item in payload.get("jobs", [])
    ]


def _lever_jobs(company: str, token: str) -> list[Job]:
    payload = _get_json(f"https://api.lever.co/v0/postings/{token}?mode=json")
    return [
        Job(
            external_id=f"lever:{token}:{item['id']}",
            title=item.get("text", "Untitled role"),
            company=company,
            location=item.get("categories", {}).get("location", "Unknown location"),
            source="Lever",
            url=item.get("hostedUrl", ""),
            description=item.get("descriptionPlain", item.get("description", "")),
        )
        for item in payload
    ]


def fetch_company_boards(path: Path) -> list[Job]:
    boards = json.loads(path.read_text(encoding="utf-8"))
    jobs: list[Job] = []
    for board in boards:
        company = board["company"]
        token = board["token"]
        ats = board["ats"].lower()
        if ats == "greenhouse":
            jobs.extend(_greenhouse_jobs(company, token))
        elif ats == "lever":
            jobs.extend(_lever_jobs(company, token))
        else:
            raise ValueError(f"Unsupported ATS '{ats}' for {company}. Use greenhouse or lever.")
    return jobs
