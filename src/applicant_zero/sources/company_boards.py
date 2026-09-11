import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen

from ..scoring import Job


@dataclass(frozen=True)
class BoardReport:
    company: str
    status: str
    job_count: int
    message: str = ""


def _get_json(url: str) -> dict | list:
    # Public career-board APIs occasionally reject Python's anonymous default
    # user agent. This identifies the private, read-only discovery client; it
    # does not evade an access control or retry around a rejected request.
    request = Request(url, headers={"User-Agent": "Applicant-Zero/0.1 (private job discovery)"})
    with urlopen(request, timeout=12) as response:
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


def _plain_text(value: object) -> str:
    """Flatten public job-detail content without depending on its HTML layout."""
    if isinstance(value, str):
        return re.sub(r"<[^>]+>", " ", value)
    if isinstance(value, dict):
        return " ".join(_plain_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_plain_text(item) for item in value)
    return ""


def _smartrecruiters_jobs(company: str, token: str) -> list[Job]:
    """Read an employer's public SmartRecruiters board and its detail records."""
    payload = _get_json(f"https://api.smartrecruiters.com/v1/companies/{token}/postings?limit=100&offset=0")
    postings = payload.get("content", []) if isinstance(payload, dict) else []
    jobs: list[Job] = []
    for item in postings:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        posting_id = str(item["id"])
        detail: dict | list = {}
        try:
            detail = _get_json(f"https://api.smartrecruiters.com/v1/companies/{token}/postings/{posting_id}")
        except (OSError, ValueError, KeyError, TypeError):
            # The public listing is still useful for title and location review
            # when a single detail record is unavailable.
            detail = {}
        location = item.get("location", {}) if isinstance(item.get("location"), dict) else {}
        location_text = ", ".join(str(location.get(key, "")).strip() for key in ("city", "region", "country") if str(location.get(key, "")).strip()) or "Unknown location"
        detail_dict = detail if isinstance(detail, dict) else {}
        description = _plain_text(detail_dict.get("jobAd", detail_dict)) or _plain_text(item)
        url = str(detail_dict.get("jobAdUrl") or detail_dict.get("applyUrl") or item.get("jobAdUrl") or f"https://jobs.smartrecruiters.com/{token}/{posting_id}")
        jobs.append(Job(
            external_id=f"smartrecruiters:{token}:{posting_id}",
            title=str(item.get("name", "Untitled role")),
            company=company,
            location=location_text,
            source="SmartRecruiters",
            url=url,
            description=description,
        ))
    return jobs


def _workable_jobs(company: str, token: str) -> list[Job]:
    """Read a Workable hosted public careers feed.

    This uses Workable's documented public account endpoint, not its employer
    REST API. The identifier is the public account subdomain from an
    ``apply.workable.com`` link, and no employer or candidate credential is
    accepted or needed.
    """
    payload = _get_json(f"https://www.workable.com/api/accounts/{token}?details=true")
    rows = payload.get("jobs", []) if isinstance(payload, dict) else []
    jobs: list[Job] = []
    for item in rows:
        if not isinstance(item, dict) or not item.get("shortcode"):
            continue
        locations = item.get("locations", [])
        location_values = []
        if isinstance(locations, list):
            for location in locations:
                if isinstance(location, dict):
                    value = ", ".join(str(location.get(key, "")).strip() for key in ("city", "region", "country") if str(location.get(key, "")).strip())
                    if value:
                        location_values.append(value)
        location = " / ".join(dict.fromkeys(location_values)) or ", ".join(str(item.get(key, "")).strip() for key in ("city", "state", "country") if str(item.get(key, "")).strip()) or "Unknown location"
        metadata = " ".join(str(item.get(key, "")).strip() for key in ("employment_type", "experience", "function") if str(item.get(key, "")).strip())
        description = _plain_text(item.get("description", ""))
        if metadata:
            description = f"{description}\nRole metadata: {metadata}".strip()
        shortcode = str(item["shortcode"])
        jobs.append(Job(
            external_id=f"workable:{token}:{shortcode}",
            title=str(item.get("title", "Untitled role")),
            company=company,
            location=location,
            source="Workable",
            url=str(item.get("url") or item.get("shortlink") or f"https://apply.workable.com/j/{shortcode}"),
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
        if not company or not token or ats not in {"greenhouse", "lever", "ashby", "smartrecruiters", "workable"}:
            reports.append(BoardReport(company or f"Board entry {index}", "unavailable", 0, "Each board needs a company, token, and supported ATS type."))
            continue
        key = (ats, token.casefold())
        if key in seen:
            reports.append(BoardReport(company, "unavailable", 0, "Duplicate ATS board token was skipped."))
            continue
        seen.add(key)
        valid.append({"company": company, "token": token, "ats": ats})
    return valid, reports


def fetch_public_board(company: str, ats: str, token: str) -> list[Job]:
    """Read one supported public board so onboarding can validate it first."""
    handlers = {
        "greenhouse": _greenhouse_jobs,
        "lever": _lever_jobs,
        "ashby": _ashby_jobs,
        "smartrecruiters": _smartrecruiters_jobs,
        "workable": _workable_jobs,
    }
    try:
        handler = handlers[ats.lower()]
    except KeyError as error:
        raise ValueError(f"Unsupported ATS '{ats}'.") from error
    return handler(company, token)


def fetch_company_boards_with_report(path: Path) -> tuple[list[Job], list[BoardReport]]:
    boards, configuration_reports = _load_valid_boards(path)
    def fetch_one(board: dict) -> tuple[list[Job], BoardReport]:
        company = board["company"]
        try:
            board_jobs = fetch_public_board(company, board["ats"], board["token"])
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
