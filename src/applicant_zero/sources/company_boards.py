import json
import re
from datetime import date
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen

from ..scoring import Job
from ..taxonomy import classify_lane
from .metadata import append_listing_metadata


_WORKDAY_ROLE_TERMS = (
    "data", "analyst", "support", "admin", "business", "operations",
    "technology", "coordinator", "reporting", "systems", "service desk", "information",
)


def _workday_search_terms(company: str, token: str, today: date | None = None) -> tuple[str, ...]:
    """Return ordinary, Sydney-focused, and rotating candidate-role searches.

    A large Workday board can contain thousands of postings. The normal board
    view is useful for general freshness, while an explicit Sydney search
    prevents globally sorted boards from burying local jobs. The final three
    bounded searches rotate through the candidate role families each day. The
    five public requests remain the hard limit, with no location guessing or
    unbounded pagination.
    """
    day = today or date.today()
    seed = sum(ord(character) for character in f"{company.casefold()}|{token.casefold()}") + day.toordinal()
    start = seed % len(_WORKDAY_ROLE_TERMS)
    terms = tuple(_WORKDAY_ROLE_TERMS[(start + offset) % len(_WORKDAY_ROLE_TERMS)] for offset in range(3))
    return ("", "sydney", *terms)


_LOCAL_DETAIL_MARKERS = (
    "sydney", "nsw", "new south wales", "australia", "remote", "unknown location",
    "parramatta", "north sydney", "macquarie park", "chatswood", "barangaroo", "pyrmont",
    "surry hills", "redfern", "alexandria", "mascot", "st leonards", "ryde", "rhodes",
    "homebush", "sydney olympic park", "strathfield", "burwood", "bankstown", "liverpool",
    "blacktown", "penrith", "castle hill", "baulkham hills", "bella vista", "milsons point",
    "circular quay", "botany", "waterloo", "wetherill park", "moorebank", "seven hills",
    "eastern creek", "huntingwood", "silverwater", "granville", "lidcombe", "campsie",
    "hurstville", "kingsgrove", "rosebery", "artarmon", "lane cove", "north ryde",
    "pymble", "hornsby", "brookvale", "manly", "crows nest", "neutral bay", "petersham",
    "newtown", "bondi junction", "regents park", "dural",
)


@dataclass(frozen=True)
class BoardReport:
    company: str
    status: str
    job_count: int
    message: str = ""
    ats: str = ""
    request_count: int = 0
    token: str = ""


def _get_json(url: str) -> dict | list:
    # Public career-board APIs occasionally reject Python's anonymous default
    # user agent. This identifies the private, read-only discovery client; it
    # does not evade an access control or retry around a rejected request.
    request = Request(url, headers={"User-Agent": "Applicant-Zero/0.1 (private job discovery)"})
    with urlopen(request, timeout=12) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(url: str, payload: dict) -> dict | list:
    """Read a documented public careers endpoint using its ordinary JSON POST."""
    request = Request(
        url, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={
            "User-Agent": "Applicant-Zero/0.1 (private job discovery)",
            "Content-Type": "application/json",
        },
    )
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
            description=append_listing_metadata(item.get("content", ""), posted_at=item.get("updated_at", item.get("created_at", ""))),
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
            description=append_listing_metadata(
                item.get("descriptionPlain", item.get("description", "")),
                posted_at=item.get("createdAt", item.get("created_at", "")),
                employment_type=item.get("categories", {}).get("commitment", "") if isinstance(item.get("categories"), dict) else "",
            ),
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
            description=append_listing_metadata(
                description, posted_at=item.get("publishedAt", item.get("createdAt", "")),
                employment_type=item.get("employmentType", ""), salary=salary,
            ),
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


def _candidate_detail_location_priority(location: str) -> int:
    """Prioritise local detail reads when a public board yields many matches.

    The twelve-record cap protects public employer endpoints. A globally sorted
    board can otherwise spend the entire cap on generic Australia or remote
    roles before a Sydney record returned by the same search receives its
    description. This only orders already-eligible public listings; it does
    not broaden the request budget or infer a location.
    """
    normalized = location.casefold().strip()
    local_markers = tuple(marker for marker in _LOCAL_DETAIL_MARKERS if marker not in {"australia", "remote", "unknown location"})
    if "sydney" in normalized or "nsw" in normalized or "new south wales" in normalized or any(marker in normalized for marker in local_markers):
        return 0
    if "australia" in normalized:
        return 1
    if "remote" in normalized:
        return 2
    return 3


def _needs_candidate_detail(title: str, location: str) -> bool:
    """Keep public detail reads for plausible candidate-lane Sydney roles.

    Global ATS boards commonly expose hundreds of roles. A role with an
    explicit overseas/interstate location is still retained long enough for
    ordinary local scoring to reject it, but it does not need an extra public
    description request. Generic Australia and unknown locations remain
    eligible because their detail can contain the decisive Sydney arrangement.
    """
    if classify_lane(title) is None:
        return False
    normalized_location = location.casefold().strip()
    return not normalized_location or any(marker in normalized_location for marker in _LOCAL_DETAIL_MARKERS)


def _smartrecruiters_jobs(company: str, token: str) -> list[Job]:
    """Read an employer's public SmartRecruiters board and detail records.

    SmartRecruiters returns a page of up to one hundred postings.  Large
    employers commonly have more than one page, so read up to five public
    pages (five hundred postings). Candidate-lane titles receive public detail
    reads, capped at twelve per board; other listings retain their public
    title and location for normal local filtering. This keeps a large board
    from turning a scheduled refresh into an unbounded crawl.
    """
    postings: list[dict] = []
    total: int | None = None
    for offset in range(0, 500, 100):
        payload = _get_json(f"https://api.smartrecruiters.com/v1/companies/{token}/postings?limit=100&offset={offset}")
        if not isinstance(payload, dict):
            break
        page = [item for item in payload.get("content", []) if isinstance(item, dict)]
        postings.extend(page)
        if total is None:
            try:
                total = max(0, int(payload.get("totalFound", payload.get("total", len(page)))))
            except (TypeError, ValueError):
                total = len(page)
        if len(page) < 100 or len(postings) >= total:
            break
    valid_postings = [item for item in postings if item.get("id")]

    def detail_for(item: dict) -> dict | list:
        posting_id = str(item["id"])
        try:
            return _get_json(f"https://api.smartrecruiters.com/v1/companies/{token}/postings/{posting_id}")
        except (OSError, ValueError, KeyError, TypeError):
            # The public listing is still useful for title and location review
            # when a single detail record is unavailable.
            return {}

    # Detail records carry the descriptions needed for accurate local scoring,
    # but reading every detail from a 500-listing board would be disproportionate.
    # The title is enough to choose which candidate-lane records merit a bounded
    # public detail request. ``map`` preserves a stable local ordering.
    def listing_location(item: dict) -> str:
        location = item.get("location", {})
        if not isinstance(location, dict):
            return str(location)
        return ", ".join(str(location.get(key, "")) for key in ("city", "region", "country"))

    detail_candidates = sorted(
        (
            item for item in valid_postings
            if _needs_candidate_detail(str(item.get("name", "")), listing_location(item))
        ),
        key=lambda item: _candidate_detail_location_priority(listing_location(item)),
    )[:12]
    with ThreadPoolExecutor(max_workers=min(6, len(detail_candidates) or 1), thread_name_prefix="applicant-zero-sr") as executor:
        details = list(executor.map(detail_for, detail_candidates))
    details_by_id = {
        str(item["id"]): detail
        for item, detail in zip(detail_candidates, details)
    }

    jobs: list[Job] = []
    for item in valid_postings:
        posting_id = str(item["id"])
        detail = details_by_id.get(posting_id, {})
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
            description=append_listing_metadata(
                description, posted_at=item.get("releasedDate", item.get("createdOn", "")),
                employment_type=detail_dict.get("employmentType", item.get("typeOfEmployment", "")),
            ),
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
            description=append_listing_metadata(
                description, posted_at=item.get("created_at", item.get("published_at", "")),
                employment_type=item.get("employment_type", ""),
            ),
        ))
    return jobs


def _workday_jobs(company: str, token: str) -> list[Job]:
    """Read a Workday public careers search endpoint with a bounded page cap.

    The token is ``host/site`` (for example
    ``example.wd3.myworkdayjobs.com/ExampleCareers``), derived from an
    employer's public Workday URL. This route uses the same read-only public
    endpoint that the careers page uses. It does not accept a login, session
    cookie or employer API credential. A five-page cap avoids one unusually
    large board consuming an unbounded discovery run.
    """
    host, separator, site = token.partition("/")
    tenant = host.split(".", 1)[0]
    if not separator or not host.endswith("myworkdayjobs.com") or not site or not tenant:
        raise ValueError("Workday board token must be host/site from a public careers URL.")
    endpoint = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    rows: list[dict] = []
    total = 0
    # The public CXS endpoint accepts at most 20 listings in one request.
    # Asking for 100 makes many otherwise-working Workday boards return 400
    # or 500. Five ordinary pages keep the existing bounded-board policy while
    # making those boards usable again.
    page_size = 20
    # A large global employer board often sorts the first page by its own
    # default order, which can hide a Sydney analyst or support role far down
    # the listing. One bounded Sydney query keeps local coverage visible; the
    # final three requests rotate through the role families this workspace
    # searches.
    queries = _workday_search_terms(company, token)
    for query_index, search_text in enumerate(queries):
        offset = 0
        payload = _post_json(endpoint, {
            "appliedFacets": {}, "limit": page_size, "offset": offset, "searchText": search_text,
        })
        page = payload.get("jobPostings", []) if isinstance(payload, dict) else []
        page_rows = [item for item in page if isinstance(item, dict)]
        rows.extend(page_rows)
        if query_index == 0 and isinstance(payload, dict):
            try:
                total = max(0, int(payload.get("total", len(page_rows))))
            except (TypeError, ValueError):
                total = len(page_rows)
        # A small board is complete after its ordinary first page, so avoid
        # unnecessary searches. Large boards use all five bounded queries.
        if query_index == 0 and (len(page_rows) < page_size or len(rows) >= total):
            break
    # Searches overlap (for example "data" and "analyst" can both return a
    # business-data analyst). Preserve first-seen order while keeping one
    # canonical public posting per employer board.
    deduplicated: dict[str, dict] = {}
    for item in rows:
        external_path = str(item.get("externalPath", "")).strip()
        identifier = external_path or str(item.get("title", "")).strip()
        if identifier and identifier not in deduplicated:
            deduplicated[identifier] = item
    rows = list(deduplicated.values())
    # Listing searches provide titles and locations but not requirements. Read
    # details only for titles that already match a candidate role lane, with a
    # hard cap so a large employer board remains bounded and courteous.
    detail_by_path: dict[str, dict] = {}
    detail_candidates = sorted(
        (
            item for item in rows
            if str(item.get("externalPath", "")).strip() and _needs_candidate_detail(
                str(item.get("title", "")), str(item.get("locationsText", "")),
            )
        ),
        key=lambda item: _candidate_detail_location_priority(str(item.get("locationsText", ""))),
    )[:12]
    for item in detail_candidates:
        external_path = str(item["externalPath"]).strip()
        detail_path = _workday_detail_path(external_path, site)
        try:
            detail = _get_json(f"https://{host}/wday/cxs/{tenant}/{site}{detail_path}")
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if isinstance(detail, dict):
            detail_by_path[external_path] = detail
    jobs: list[Job] = []
    for item in rows:
        external_path = str(item.get("externalPath", "")).strip()
        identifier = external_path or str(item.get("title", "")).strip()
        if not identifier:
            continue
        detail = detail_by_path.get(external_path, {})
        info = detail.get("jobPostingInfo", {}) if isinstance(detail.get("jobPostingInfo"), dict) else {}
        description = _plain_text(info.get("jobDescription", ""))
        detail = append_listing_metadata(
            description, posted_at=info.get("postedOn", item.get("postedOn", "")),
            employment_type=info.get("timeType", item.get("timeType", item.get("workerSubType", ""))),
        )
        jobs.append(Job(
            external_id=f"workday:{host}:{site}:{identifier}",
            title=str(item.get("title", "Untitled role")),
            company=company,
            location=str(item.get("locationsText", "Unknown location")),
            source="Workday",
            url=f"https://{host}{external_path}" if external_path.startswith("/") else f"https://{host}",
            description=detail,
        ))
    return jobs


def _workday_detail_path(external_path: str, site: str) -> str:
    """Normalise a public Workday job path for its CXS detail endpoint."""
    parts = [part for part in external_path.split("/") if part]
    # Most CXS responses already provide ``/job/...``. Some tenants return
    # their visitor-facing ``/en-US/Site/job/...`` form instead.
    if len(parts) >= 3 and re.fullmatch(r"[a-z]{2}-[A-Z]{2}", parts[0]) and parts[1] == site:
        parts = parts[2:]
    return "/" + "/".join(parts)


def _recruitee_jobs(company: str, token: str) -> list[Job]:
    """Read currently-public Recruitee offer feeds.

    Recruitee has announced that its Careers Site API will require an employer
    token from February 2027. This adapter is read-only and transitional: an
    authentication response becomes an unavailable-board report, never a
    prompt to obtain an employer credential.
    """
    payload = _get_json(f"https://{token}.recruitee.com/api/offers/")
    offers = payload.get("offers", []) if isinstance(payload, dict) else []
    jobs: list[Job] = []
    for item in offers:
        if not isinstance(item, dict) or str(item.get("status", "published")).lower() not in {"published", "open"}:
            continue
        identifier = item.get("id") or item.get("slug")
        if not identifier:
            continue
        locations = item.get("locations", [])
        values = [str(row.get("name") or row.get("city") or "").strip() for row in locations if isinstance(row, dict)] if isinstance(locations, list) else []
        location = ", ".join(value for value in values if value) or str(item.get("location", "Unknown location"))
        jobs.append(Job(
            external_id=f"recruitee:{token}:{identifier}",
            title=str(item.get("title", "Untitled role")),
            company=company,
            location=location,
            source="Recruitee",
            url=str(item.get("careers_url") or item.get("careers_apply_url") or ""),
            description=append_listing_metadata(
                str(item.get("description") or item.get("description_html") or ""),
                posted_at=item.get("created_at", item.get("published_at", "")),
                employment_type=item.get("employment_type", ""),
            ),
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
        if not company or not token or ats not in {"greenhouse", "lever", "ashby", "smartrecruiters", "workable", "recruitee", "workday"}:
            reports.append(BoardReport(company or f"Board entry {index}", "unavailable", 0, "Each board needs a company, token, and supported ATS type."))
            continue
        key = (ats, token.casefold())
        if key in seen:
            reports.append(BoardReport(company, "unavailable", 0, "Duplicate ATS board token was skipped."))
            continue
        seen.add(key)
        valid.append({"company": company, "token": token, "ats": ats})
    return valid, reports


def public_board_identity_prefix(ats: str, token: str) -> str:
    """Return the stable external-id namespace for one configured board.

    One employer can expose more than one board on the same ATS. Snapshot
    retirement must therefore be scoped to the board token, not just company
    and provider, so a successful empty board never hides its sibling board.
    """
    normalized_ats = ats.casefold().strip()
    normalized_token = token.strip()
    if normalized_ats == "workday":
        normalized_token = normalized_token.replace("/", ":")
    return f"{normalized_ats}:{normalized_token}:"


def fetch_public_board(company: str, ats: str, token: str) -> list[Job]:
    """Read one supported public board so onboarding can validate it first."""
    handlers = {
        "greenhouse": _greenhouse_jobs,
        "lever": _lever_jobs,
        "ashby": _ashby_jobs,
        "smartrecruiters": _smartrecruiters_jobs,
        "workable": _workable_jobs,
        "recruitee": _recruitee_jobs,
        "workday": _workday_jobs,
    }
    try:
        handler = handlers[ats.lower()]
    except KeyError as error:
        raise ValueError(f"Unsupported ATS '{ats}'.") from error
    return handler(company, token)


def _request_count_for_board(ats: str, jobs: int | list[Job]) -> int:
    """Return a transparent bounded request estimate for public board reads.

    Callers that have the mapped listings can include Workday detail reads in
    the count.  The integer form remains useful for configuration and tests
    where only a listing count is available.
    """
    job_count = jobs if isinstance(jobs, int) else len(jobs)
    normalized = ats.casefold()
    if normalized == "workday":
        # Workday accepts at most 20 jobs per public search page. Small boards
        # finish in one request; a larger board uses four targeted role-family
        # queries in addition to the ordinary first page.
        listing_requests = 1 if max(0, job_count) <= 20 else 5
        if isinstance(jobs, int):
            return listing_requests
        detail_requests = min(12, sum(
            _needs_candidate_detail(job.title, job.location) for job in jobs
        ))
        return listing_requests + detail_requests
    if normalized == "smartrecruiters":
        # One request for each 100-posting public listing page (capped at five)
        # plus at most twelve candidate-lane detail reads.  The integer form
        # cannot know which titles qualify, so it reports the safe upper bound
        # under the same cap rather than incorrectly counting every listing.
        listing_pages = max(1, min(5, (max(0, job_count) + 99) // 100))
        if isinstance(jobs, int):
            return listing_pages + min(12, max(0, job_count))
        detail_requests = min(12, sum(
            _needs_candidate_detail(job.title, job.location) for job in jobs
        ))
        return listing_pages + detail_requests
    return 1


def fetch_company_boards_with_report(path: Path) -> tuple[list[Job], list[BoardReport]]:
    boards, configuration_reports = _load_valid_boards(path)
    def fetch_one(board: dict) -> tuple[list[Job], BoardReport]:
        company = board["company"]
        try:
            board_jobs = fetch_public_board(company, board["ats"], board["token"])
        except (OSError, ValueError, KeyError, TypeError) as error:
            return [], BoardReport(company, "unavailable", 0, str(error), board["ats"].title(), 1, board["token"])
        return board_jobs, BoardReport(
            company, "checked", len(board_jobs), "", board["ats"].title(),
            _request_count_for_board(board["ats"], board_jobs), board["token"],
        )

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
