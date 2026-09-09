import json
from concurrent.futures import ThreadPoolExecutor
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
    with urlopen(url, timeout=12) as response:
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


def _load_valid_boards(path: Path) -> tuple[list[dict], list[BoardReport]]:
    """Keep one bad private board entry from stopping all scheduled discovery."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as error:
        return [], [BoardReport("Career board configuration", "unavailable", 0, str(error))]
    if not isinstance(payload, list):
        return [], [BoardReport("Career board configuration", "unavailable", 0, "Board configuration must be a JSON list.")]
    valid: list[dict] = []
    reports: list[BoardReport] = []
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            reports.append(BoardReport(f"Board entry {index}", "unavailable", 0, "Board entry must be an object."))
            continue
        company = str(item.get("company", "")).strip()
        token = str(item.get("token", "")).strip()
        ats = str(item.get("ats", "")).strip().lower()
        if not company or not token or ats not in {"greenhouse", "lever", "ashby"}:
            reports.append(BoardReport(company or f"Board entry {index}", "unavailable", 0, "Each board needs a company, token, and supported ATS type."))
            continue
        key = (ats, token.casefold())
        if key in seen:
            reports.append(BoardReport(company, "unavailable", 0, "Duplicate ATS board token was skipped."))
            continue
        seen.add(key)
        valid.append({"company": company, "token": token, "ats": ats})
    return valid, reports


def fetch_company_boards_with_report(path: Path) -> tuple[list[Job], list[BoardReport]]:
    boards, configuration_reports = _load_valid_boards(path)
    def fetch_one(board: dict) -> tuple[list[Job], BoardReport]:
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
            return [], BoardReport(company, "unavailable", 0, str(error))
        return board_jobs, BoardReport(company, "checked", len(board_jobs))

    # Board APIs are independent. Parallel requests keep one slow employer
    # endpoint from holding up every other source during scheduled refreshes.
    if not boards:
        return [], configuration_reports
    with ThreadPoolExecutor(max_workers=min(8, len(boards)), thread_name_prefix="applicant-zero-board") as executor:
        results = list(executor.map(fetch_one, boards))
    jobs: list[Job] = []
    reports: list[BoardReport] = list(configuration_reports)
    for board_jobs, report in results:
        jobs.extend(board_jobs)
        reports.append(report)
    return jobs, reports
