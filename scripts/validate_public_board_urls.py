"""Validate a bounded batch of explicit public ATS careers URLs.

This is an onboarding helper for a reviewed employer research list. It never
searches for an employer, guesses a URL, signs in, or writes the private board
registry. It simply checks whether the named public ATS board can be read,
then writes the successful rows for the normal private importer.
"""

from __future__ import annotations

import csv
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from applicant_zero.discovery_registry import public_board_from_url
from applicant_zero.sources.company_boards import fetch_public_board


def load_rows(path: Path) -> list[dict[str, str]]:
    """Read CSV or JSON input rows containing company and careers_url."""
    if path.suffix.casefold() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        rows = payload.get("boards", []) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise ValueError("JSON must be a list or contain a boards list.")
        return [{str(key): str(value or "") for key, value in row.items()} for row in rows if isinstance(row, dict)]
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [{key: value or "" for key, value in row.items()} for row in csv.DictReader(handle)]


def validate_rows(rows: list[dict[str, str]], *, limit: int = 60) -> tuple[list[dict[str, str]], list[str]]:
    """Return readable public boards and clear errors for malformed rows.

    Empty public boards are accepted: a successful empty response is still a
    valid employer board and may have listings on a later refresh. The limit is
    deliberate so a spreadsheet cannot turn this helper into an unbounded
    crawl.
    """
    candidates: list[tuple[str, str, str, str]] = []
    rejected: list[str] = []
    seen: set[tuple[str, str]] = set()
    for index, row in enumerate(rows, start=2):
        company = str(row.get("company", "")).strip()
        url = str(row.get("careers_url", row.get("board_url", ""))).strip()
        try:
            ats, token = public_board_from_url(url)
        except ValueError as error:
            rejected.append(f"{company or f'row {index}'}: {error}")
            continue
        key = (ats, token.casefold())
        if not company:
            rejected.append(f"row {index}: missing company")
        elif key not in seen:
            seen.add(key)
            candidates.append((company, url, ats, token))
    candidates = candidates[:max(0, min(limit, 200))]

    def validate(candidate: tuple[str, str, str, str]) -> tuple[dict[str, str] | None, str | None]:
        company, url, ats, token = candidate
        try:
            jobs = fetch_public_board(company, ats, token)
        except (OSError, ValueError, KeyError, TypeError) as error:
            return None, f"{company}: public board unavailable ({error})"
        return {
            "company": company, "careers_url": url, "ats": ats,
            "token": token, "listing_count": str(len(jobs)),
        }, None

    if not candidates:
        return [], rejected
    with ThreadPoolExecutor(max_workers=min(8, len(candidates)), thread_name_prefix="applicant-zero-validate") as executor:
        results = list(executor.map(validate, candidates))
    accepted = [row for row, _ in results if row is not None]
    rejected.extend(error for _, error in results if error)
    return accepted, rejected


def main() -> None:
    if len(sys.argv) not in {3, 4}:
        raise SystemExit("Usage: python scripts/validate_public_board_urls.py reviewed_boards.csv-or-json validated_boards.json [max_boards]")
    source, output = Path(sys.argv[1]).expanduser(), Path(sys.argv[2]).expanduser()
    limit = int(sys.argv[3]) if len(sys.argv) == 4 else 60
    accepted, rejected = validate_rows(load_rows(source), limit=limit)
    output.write_text(json.dumps(accepted, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Validated {len(accepted)} public board(s); {len(rejected)} skipped. Output: {output}")
    for detail in rejected:
        print(f"SKIPPED · {detail}")


if __name__ == "__main__":
    main()
