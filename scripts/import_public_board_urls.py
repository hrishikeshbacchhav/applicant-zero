"""Import reviewed public ATS careers URLs into Applicant Zero's private registry.

CSV columns: company,careers_url
The script stores only a public board identifier. It does not log in, crawl
arbitrary pages or fetch jobs; the next normal refresh validates configured
boards with their supported public feed.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from applicant_zero.discovery_registry import add_public_board_urls
from applicant_zero.runtime import state_root


def _validate_rows(rows: object) -> list[dict[str, str]]:
    if isinstance(rows, dict):
        rows = rows.get("boards", rows.get("jobs", []))
    if not isinstance(rows, list):
        raise ValueError("JSON must be a list of board rows or an object with a boards list.")
    cleaned = [{str(key): str(value or "") for key, value in row.items()}
               for row in rows if isinstance(row, dict)]
    if not cleaned:
        return []
    if not any("company" in row for row in cleaned):
        raise ValueError("Each row must contain a company field.")
    if not any("careers_url" in row or "board_url" in row for row in cleaned):
        raise ValueError("Each row must contain a careers_url or board_url field.")
    return cleaned


def load_rows(path: Path) -> list[dict[str, str]]:
    """Load reviewed board rows from CSV or the research extractor's JSON."""
    if path.suffix.casefold() == ".json":
        try:
            return _validate_rows(json.loads(path.read_text(encoding="utf-8-sig")))
        except json.JSONDecodeError as error:
            raise ValueError(f"Could not read JSON: {error}") from error
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "company" not in reader.fieldnames:
            raise ValueError("CSV must contain a company column.")
        if "careers_url" not in reader.fieldnames and "board_url" not in reader.fieldnames:
            raise ValueError("CSV must contain a careers_url column.")
        return _validate_rows([{key: value or "" for key, value in row.items()} for row in reader])


def import_rows(state_directory: Path, starter_path: Path, rows: list[dict[str, str]]) -> tuple[int, int, list[str]]:
    """Store already-reviewed CSV or JSON rows in a caller-selected private registry."""
    return add_public_board_urls(state_directory, starter_path, rows)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/import_public_board_urls.py path/to/public_boards.csv-or-json")
    source = Path(sys.argv[1]).expanduser()
    rows = load_rows(source)
    created, existing, rejected = import_rows(
        state_root(ROOT), ROOT / "data" / "company_boards.starter.json", rows
    )
    print(f"Saved {created} public board(s); {existing} already existed; {len(rejected)} skipped.")
    for detail in rejected:
        print(f"SKIPPED · {detail}")


if __name__ == "__main__":
    main()
