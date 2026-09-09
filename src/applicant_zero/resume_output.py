"""Create a private editable resume copy for one reviewed job."""

import re
import shutil
import sqlite3
from pathlib import Path

from .private_profile import load_profile
from .storage import get_match


def _output_path(database_path: Path, row: dict) -> Path:
    safe = re.sub(r"[^a-z0-9]+", "-", f"{row['company']}-{row['title']}".lower()).strip("-")
    return database_path.parent.parent / "private" / "application_packets" / f"{safe}-tailored-resume.docx"


def create_editable_resume_copy(database_path: Path, external_id: str) -> Path:
    with sqlite3.connect(database_path) as connection:
        row = get_match(connection, external_id)
    if row is None:
        raise ValueError("Job not found.")
    profile = load_profile(database_path.parent.parent / "private" / "candidate_profile.json")
    if not profile:
        raise ValueError("Private candidate profile is not ready.")
    master = Path(profile.get("editable_resume_masters", {}).get(row["resume_family"], ""))
    if master.suffix.lower() != ".docx" or not master.exists():
        raise ValueError("The selected résumé family does not have an editable Word master.")
    output = _output_path(database_path, row)
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(master, output)
    return output


def editable_resume_copy_exists(database_path: Path, external_id: str) -> bool:
    with sqlite3.connect(database_path) as connection:
        row = get_match(connection, external_id)
    return bool(row and _output_path(database_path, row).exists())
