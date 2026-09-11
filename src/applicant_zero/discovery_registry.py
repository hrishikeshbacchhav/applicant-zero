"""Validated source and target-company registries used by scheduled discovery."""

import json
import re
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DiscoverySource:
    identifier: str
    label: str
    mode: str
    cadence: str
    role_lanes: tuple[str, ...]


@dataclass(frozen=True)
class TargetCompany:
    company: str
    sector: str
    priority: int


SUPPORTED_PUBLIC_ATS = {"greenhouse", "lever", "ashby", "smartrecruiters", "workable", "recruitee"}


def public_board_from_url(value: str) -> tuple[str, str]:
    """Recognise a supported public careers URL without following it or scraping.

    Only the provider's hosted public-board URL shapes are accepted.  A normal
    employer web page, individual job link, credential URL or arbitrary domain
    is deliberately rejected so the candidate can choose the correct public
    careers page instead.
    """
    url = urlparse(value.strip())
    host = url.netloc.casefold().split(":", 1)[0]
    parts = [part for part in url.path.split("/") if part]
    token = ""
    ats = ""
    if host in {"boards.greenhouse.io", "job-boards.greenhouse.io"} and parts:
        ats, token = "greenhouse", parts[0]
    elif host in {"jobs.lever.co", "jobs.eu.lever.co"} and parts:
        ats, token = "lever", parts[0]
    elif host == "jobs.ashbyhq.com" and parts:
        ats, token = "ashby", parts[0]
    elif host in {"jobs.smartrecruiters.com", "careers.smartrecruiters.com"} and parts:
        ats, token = "smartrecruiters", parts[0]
    elif host == "apply.workable.com" and parts and parts[0] != "j":
        ats, token = "workable", parts[0]
    elif host == "www.workable.com" and parts[:3] == ["api", "accounts"] and len(parts) >= 3:
        ats, token = "workable", parts[2]
    elif host.endswith(".recruitee.com") and host.count(".") >= 2:
        ats, token = "recruitee", host.split(".", 1)[0]
    if ats and re.fullmatch(r"[A-Za-z0-9._-]{2,180}", token):
        return ats, token
    raise ValueError("Use a supported public Greenhouse, Lever, Ashby, SmartRecruiters, Workable or Recruitee careers URL.")


def add_public_board_url(state_root: Path, starter_path: Path, company: str, public_url: str) -> tuple[dict[str, str], bool]:
    ats, token = public_board_from_url(public_url)
    return add_public_board(state_root, starter_path, company, ats, token)


def add_public_board(state_root: Path, starter_path: Path, company: str, ats: str, token: str) -> tuple[dict[str, str], bool]:
    """Save a verified public career board in the private runtime.

    The starter boards are copied on first use, so adding one board from the
    dashboard never hides the maintained starter coverage.  This stores only
    the public employer board identifier, never an employer or candidate key.
    """
    clean_company = company.strip()
    clean_ats = ats.strip().lower()
    clean_token = token.strip()
    if not clean_company or len(clean_company) > 160:
        raise ValueError("Enter the employer name.")
    if clean_ats not in SUPPORTED_PUBLIC_ATS:
        raise ValueError("Choose Greenhouse, Lever, Ashby, SmartRecruiters, Workable or Recruitee.")
    if not re.fullmatch(r"[A-Za-z0-9._-]{2,180}", clean_token):
        raise ValueError("Enter the public board token from the employer careers URL.")

    destination = state_root / "data" / "company_boards.json"
    seed = _load(starter_path) if starter_path.exists() else []
    existing = _load(destination) if destination.exists() else []
    merged: list[dict] = []
    known: set[tuple[str, str]] = set()
    for row in [*seed, *existing]:
        if not isinstance(row, dict):
            continue
        row_ats = str(row.get("ats", "")).strip().lower()
        row_token = str(row.get("token", "")).strip()
        if row_ats not in SUPPORTED_PUBLIC_ATS or not row_token:
            continue
        key = (row_ats, row_token.casefold())
        if key in known:
            continue
        known.add(key)
        merged.append({"company": str(row.get("company", "")).strip(), "ats": row_ats, "token": row_token})

    entry = {"company": clean_company, "ats": clean_ats, "token": clean_token}
    key = (clean_ats, clean_token.casefold())
    created = key not in known
    if created:
        merged.append(entry)
    else:
        entry = next(row for row in merged if (row["ats"], row["token"].casefold()) == key)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
    return entry, created


def _load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_sources(path: Path) -> list[DiscoverySource]:
    return [DiscoverySource(row["id"], row["label"], row["mode"], row["cadence"], tuple(row["role_lanes"])) for row in _load(path)]


def load_targets(path: Path) -> list[TargetCompany]:
    rows = [TargetCompany(row["company"], row["sector"], int(row["priority"])) for row in _load(path)]
    unique: dict[str, TargetCompany] = {}
    for item in rows:
        key = item.company.casefold()
        unique[key] = min(item, unique[key], key=lambda target: target.priority) if key in unique else item
    return sorted(unique.values(), key=lambda item: (item.priority, item.company))


def board_coverage(targets: list[TargetCompany], board_path: Path) -> dict[str, list[str]]:
    """Show which target companies have a verified public ATS board configured."""
    boards = _load(board_path)
    configured = {str(board.get("company", "")).casefold() for board in boards}
    covered = [target.company for target in targets if target.company.casefold() in configured]
    pending = [target.company for target in targets if target.company.casefold() not in configured]
    return {"configured": covered, "research_needed": pending}


def employer_coverage_rows(
    targets_path: Path,
    board_path: Path,
    board_checks: list[dict] | None = None,
    board_trends: dict[str, dict] | None = None,
) -> list[dict[str, object]]:
    """Return an auditable employer-by-employer coverage map for the dashboard."""
    targets = load_targets(targets_path)
    boards = _load(board_path)
    board_by_company = {
        str(board.get("company", "")).casefold(): str(board.get("ats", "")).title()
        for board in boards if isinstance(board, dict)
    }
    health_by_company = {
        str(item.get("company", "")).casefold(): str(item.get("status", "not checked"))
        for item in (board_checks or [])
    }
    rows: list[dict[str, object]] = []
    for target in targets:
        trend = (board_trends or {}).get(target.company.casefold(), {})
        rows.append({
            "company": target.company,
            "sector": target.sector,
            "priority": target.priority,
            "route": "Public ATS refresh" if target.company.casefold() in board_by_company else "Research queue",
            "ats": board_by_company.get(target.company.casefold(), ""),
            "health": health_by_company.get(target.company.casefold(), "not checked") if target.company.casefold() in board_by_company else "not applicable",
            "job_count": trend.get("job_count"),
            "job_change": trend.get("change"),
            "checked_at": trend.get("checked_at", ""),
        })
    return rows


def discovery_overview(sources_path: Path, targets_path: Path, board_path: Path) -> dict[str, object]:
    """Report discovery coverage without implying every target has a live vacancy."""
    sources = load_sources(sources_path)
    targets = load_targets(targets_path)
    coverage = board_coverage(targets, board_path)
    return {
        "source_count": len(sources),
        "automated_sources": [source.label for source in sources if source.mode == "public_ats_api"],
        "manual_sources": [source.label for source in sources if source.mode != "public_ats_api"],
        "target_count": len(targets),
        "configured_count": len(coverage["configured"]),
        "configured": coverage["configured"],
        "research_needed": coverage["research_needed"],
    }


def board_health_summary(board_path: Path, board_checks: list[dict] | None = None, stale_after_hours: int = 30) -> dict[str, int]:
    """Summarise configured-board health without treating an old check as live."""
    configured = [row for row in _load(board_path) if isinstance(row, dict)]
    checks = {str(row.get("company", "")).casefold(): row for row in (board_checks or [])}
    cutoff = datetime.now(timezone.utc) - timedelta(hours=stale_after_hours)
    checked = unavailable = stale = never_checked = 0
    for board in configured:
        report = checks.get(str(board.get("company", "")).casefold())
        if not report:
            never_checked += 1
            continue
        if str(report.get("status", "")) == "unavailable":
            unavailable += 1
            continue
        timestamp = str(report.get("checked_at", ""))
        try:
            observed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=timezone.utc)
            if observed < cutoff:
                stale += 1
                continue
        except ValueError:
            stale += 1
            continue
        checked += 1
    return {"configured": len(configured), "checked": checked, "unavailable": unavailable, "stale": stale, "never_checked": never_checked}
