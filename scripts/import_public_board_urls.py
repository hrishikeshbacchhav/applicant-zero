"""Import reviewed public ATS careers URLs into Applicant Zero's private registry.

CSV columns: company,careers_url
The script stores only a public board identifier. It does not log in, crawl
arbitrary pages or fetch jobs; the next normal refresh validates configured
boards with their supported public feed.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from applicant_zero.discovery_registry import add_public_board_urls
from applicant_zero.runtime import state_root


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "company" not in reader.fieldnames:
            raise ValueError("CSV must contain a company column.")
        if "careers_url" not in reader.fieldnames and "board_url" not in reader.fieldnames:
            raise ValueError("CSV must contain a careers_url column.")
        return [{key: value or "" for key, value in row.items()} for row in reader]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/import_public_board_urls.py path/to/public_boards.csv")
    source = Path(sys.argv[1]).expanduser()
    rows = load_rows(source)
    created, existing, rejected = add_public_board_urls(
        state_root(ROOT), ROOT / "data" / "company_boards.starter.json", rows
    )
    print(f"Saved {created} public board(s); {existing} already existed; {len(rejected)} skipped.")
    for detail in rejected:
        print(f"SKIPPED · {detail}")


if __name__ == "__main__":
    main()
