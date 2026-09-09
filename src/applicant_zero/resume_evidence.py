"""Private, read-only evidence inventory from the candidate's approved PDFs."""

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from .private_profile import load_profile


class ResumeEvidenceError(Exception):
    pass


def _fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _candidate_lines(text: str) -> list[str]:
    """Keep useful original résumé lines, without rewriting or adding claims."""
    lines: list[str] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip(" •\t-")
        if not 25 <= len(line) <= 400:
            continue
        key = line.casefold()
        if key not in seen:
            lines.append(line)
            seen.add(key)
    return lines[:80]


def _extract(path: Path) -> tuple[int, str]:
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise ResumeEvidenceError("PDF reading is unavailable. Install the optional PDF support before creating an inventory.") from error
    try:
        reader = PdfReader(str(path))
        return len(reader.pages), "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as error:
        raise ResumeEvidenceError(f"Could not read approved résumé PDF: {path.name}") from error


def inventory_path(project_root: Path) -> Path:
    return project_root / "private" / "resume_evidence_inventory.json"


def create_resume_evidence_inventory(project_root: Path) -> Path:
    """Read the approved PDFs locally and write a private audit inventory.

    The original PDFs are never changed.  Extracted wording is source material,
    not a licence to create new achievements or facts.
    """
    profile = load_profile(project_root / "private" / "candidate_profile.json")
    if not profile:
        raise ResumeEvidenceError("Private candidate profile is not ready.")
    resumes: dict[str, dict] = {}
    for family, raw_path in profile.get("resumes", {}).items():
        path = Path(str(raw_path)).expanduser()
        if not path.exists() or path.suffix.casefold() != ".pdf":
            continue
        pages, text = _extract(path)
        resumes[str(family)] = {
            "filename": path.name,
            "sha256": _fingerprint(path),
            "pages": pages,
            "source_lines": _candidate_lines(text),
        }
    if not resumes:
        raise ResumeEvidenceError("No approved résumé PDFs could be read from the private profile.")
    payload = {
        "schema_version": 1,
        "created_at": datetime.now().isoformat(timespec="minutes"),
        "rules": [
            "This inventory is private and generated from approved résumé PDFs.",
            "Use source lines as wording to verify, never as permission to invent facts or metrics.",
            "The approved PDFs and editable masters are never modified by this inventory.",
        ],
        "resumes": resumes,
    }
    output = inventory_path(project_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return output


def load_lane_resume_evidence(project_root: Path, family: str | None) -> list[str]:
    """Return exact extracted source lines for the matching résumé family."""
    path = inventory_path(project_root)
    if not family or not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [str(line) for line in payload.get("resumes", {}).get(family, {}).get("source_lines", [])]
    except (json.JSONDecodeError, AttributeError):
        return []
