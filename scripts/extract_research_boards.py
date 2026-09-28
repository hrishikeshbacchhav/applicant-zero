"""Extract supported public ATS boards from a candidate-provided XLSX research list.

This is an offline conversion step. It does not browse employer websites,
guess a careers URL, or use a password. The resulting JSON is intended for
review before passing its public URLs to the existing board importer.
"""

from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from applicant_zero.discovery_registry import public_board_from_url


MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RELATIONSHIP = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def _column_index(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference or "")
    if not letters:
        return 0
    index = 0
    for character in letters.group(0):
        index = index * 26 + ord(character) - ord("A") + 1
    return index - 1


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    return ["".join(node.itertext()) for node in root.findall(f"{MAIN}si")]


def _cell_value(cell: ElementTree.Element, shared: list[str]) -> str:
    kind = cell.get("t", "")
    if kind == "s":
        try:
            return shared[int(cell.findtext(f"{MAIN}v") or "")]
        except (IndexError, ValueError):
            return ""
    return "".join(cell.itertext()).strip()


def workbook_rows(path: Path) -> dict[str, list[list[str]]]:
    """Read text rows from a simple XLSX without requiring Excel to be open."""
    with zipfile.ZipFile(path) as archive:
        shared = _shared_strings(archive)
        relationships = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {item.get("Id", ""): item.get("Target", "").lstrip("/") for item in relationships}
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        result: dict[str, list[list[str]]] = {}
        for sheet in workbook.findall(f"{MAIN}sheets/{MAIN}sheet"):
            sheet_name = sheet.get("name", "")
            target = targets.get(sheet.get(RELATIONSHIP, ""), "")
            if not sheet_name or not target:
                continue
            root = ElementTree.fromstring(archive.read(target))
            rows: list[list[str]] = []
            for row in root.findall(f".//{MAIN}row"):
                cells = row.findall(f"{MAIN}c")
                if not cells:
                    continue
                values = [""] * (max(_column_index(cell.get("r", "")) for cell in cells) + 1)
                for cell in cells:
                    values[_column_index(cell.get("r", ""))] = _cell_value(cell, shared)
                rows.append(values)
            result[sheet_name] = rows
    return result


def research_public_boards(rows: list[list[str]]) -> list[dict[str, str]]:
    """Keep only explicit, supported public ATS URLs from research rows."""
    header_index = next((index for index, row in enumerate(rows) if any(value.strip().casefold() == "employer" for value in row)), None)
    if header_index is None:
        return []
    header = [value.strip().casefold() for value in rows[header_index]]
    employer_column = header.index("employer")
    url_column = next((index for index, value in enumerate(header) if "careers" in value and "url" in value), None)
    if url_column is None:
        return []
    boards: list[dict[str, str]] = []
    known: set[tuple[str, str]] = set()
    for row in rows[header_index + 1:]:
        company = row[employer_column].strip() if len(row) > employer_column else ""
        url = row[url_column].strip() if len(row) > url_column else ""
        if not company or not url:
            continue
        try:
            ats, token = public_board_from_url(url)
        except ValueError:
            continue
        key = (ats, token.casefold())
        if key not in known:
            known.add(key)
            boards.append({"company": company, "careers_url": url, "ats": ats, "token": token})
    return boards


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python scripts/extract_research_boards.py research.xlsx candidate_boards.json")
    sheets = workbook_rows(Path(sys.argv[1]))
    rows = sheets.get("Research Additions", [])
    boards = research_public_boards(rows)
    Path(sys.argv[2]).write_text(json.dumps(boards, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Extracted {len(boards)} supported public ATS board(s) from the research workbook.")


if __name__ == "__main__":
    main()
