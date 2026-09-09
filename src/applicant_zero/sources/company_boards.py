import json
from dataclasses import dataclass
from pathlib import Path
from urllib.request import urlopen

from ..scoring import Job


@dataclass(frozen=True)
class BoardReport:
    company: str
    status: str
    job_count: int
    message: str = ""


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


def _ashby_jobs(company: str, token: str) -> list[Job]:
    payload = _get_json(f"https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true")
    jobs = []
    for item in payload.get("jobs", []):
        if item.get("isListed") is False:
            continue
        description = item.get("descriptionPlain", item.get("descriptionHtml", ""))
        compensation = item.get("compensation", {})
        salary = compensation.get("scrapeableCompensationSalarySummary", "") if isinstance(compensation, dict) else ""
        if salary:
            description = f"{description}\nCompensation: {salary}"
        jobs.append(Job(
            external_id=f"ashby:{token}:{item.get('applyUrl', item.get('jobUrl', item.get('title', 'role')))}",
            title=item.get("title", "Untitled role"),
            company=company,
            location=item.get("location", "Unknown location"),
            source="Ashby",
            url=item.get("applyUrl", item.get("jobUrl", "")),
            description=description,
        ))
    return jobs


def fetch_company_boards(path: Path) -> list[Job]:
    jobs, reports = fetch_company_boards_with_report(path)
    failures = [report for report in reports if report.status == "unavailable"]
    if failures:
        summary = "; ".join(f"{report.company}: {report.message}" for report in failures)
        print(f"Some career boards were unavailable and were skipped: {summary}")
    return jobs


def fetch_company_boards_with_report(path: Path) -> tuple[list[Job], list[BoardReport]]:
    boards = json.loads(path.read_text(encoding="utf-8"))
    jobs: list[Job] = []
    reports: list[BoardReport] = []
    for board in boards:
        company = board["company"]
        token = board["token"]
        ats = board["ats"].lower()
        try:
            if ats == "greenhouse":
                board_jobs = _greenhouse_jobs(company, token)
            elif ats == "lever":
                board_jobs = _lever_jobs(company, token)
            elif ats == "ashby":
                board_jobs = _ashby_jobs(company, token)
            else:
                raise ValueError(f"Unsupported ATS '{ats}'. Use greenhouse, lever or ashby.")
        except (OSError, ValueError, KeyError, TypeError) as error:
            reports.append(BoardReport(company, "unavailable", 0, str(error)))
            continue
        jobs.extend(board_jobs)
        reports.append(BoardReport(company, "checked", len(board_jobs)))
    return jobs, reports
