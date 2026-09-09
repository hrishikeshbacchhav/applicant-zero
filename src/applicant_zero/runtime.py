"""Private runtime state kept outside the source checkout and cloud-sync folders."""

import os
import shutil
import sqlite3
import json
from datetime import datetime
from pathlib import Path


def state_root(repository_root: Path) -> Path:
    """Return the private state directory, overridable for testing or portability."""
    configured = os.environ.get("APPLICANT_ZERO_STATE_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return local / "Applicant Zero"


def prepare_state(repository_root: Path) -> Path:
    """Create private runtime folders and safely copy legacy private state once."""
    target = state_root(repository_root)
    target.mkdir(parents=True, exist_ok=True)
    for name in ("private", "data"):
        destination = target / name
        legacy = repository_root / name
        if not destination.exists() and legacy.exists():
            shutil.copytree(legacy, destination)
        else:
            destination.mkdir(parents=True, exist_ok=True)
    return target


def database_path(repository_root: Path) -> Path:
    return prepare_state(repository_root) / "data" / "applicant_zero.sqlite3"


def synchronise_board_registry(repository_root: Path) -> Path:
    """Merge newly verified starter boards into a candidate's private registry.

    A private board file is never overwritten: candidate-added boards and any
    custom notes remain intact, while newly shipped public boards become
    available after the next normal refresh.
    """
    state = prepare_state(repository_root)
    destination = state / "data" / "company_boards.json"
    starter = repository_root / "data" / "company_boards.starter.json"
    starter_rows = json.loads(starter.read_text(encoding="utf-8")) if starter.exists() else []
    existing_rows = []
    if destination.exists():
        try:
            existing_rows = json.loads(destination.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing_rows = []
    keys = {(str(row.get("company", "")).casefold(), str(row.get("ats", "")).casefold(), str(row.get("token", "")).casefold()) for row in existing_rows}
    merged = list(existing_rows)
    for row in starter_rows:
        key = (str(row.get("company", "")).casefold(), str(row.get("ats", "")).casefold(), str(row.get("token", "")).casefold())
        if key not in keys:
            merged.append(row)
            keys.add(key)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
    return destination


def backup_database(repository_root: Path, reason: str = "startup") -> Path | None:
    """Make an integrity-checked SQLite backup before a run.

    SQLite's backup API gives a consistent snapshot even if the dashboard has
    recently written. A plain file copy can capture only part of a transaction.
    """
    database = database_path(repository_root)
    if not database.exists() or database.stat().st_size == 0:
        return None
    backup_dir = database.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = backup_dir / f"applicant_zero-{reason}-{stamp}.sqlite3"
    temporary = backup.with_suffix(".partial.sqlite3")
    try:
        source = sqlite3.connect(database)
        destination = sqlite3.connect(temporary)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()
        check = sqlite3.connect(temporary)
        try:
            integrity = check.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            check.close()
        if integrity != "ok":
            temporary.unlink(missing_ok=True)
            return None
        temporary.replace(backup)
    except sqlite3.DatabaseError:
        temporary.unlink(missing_ok=True)
        return None
    retained = sorted(backup_dir.glob(f"applicant_zero-{reason}-*.sqlite3"), key=lambda item: item.stat().st_mtime, reverse=True)
    for old in retained[7:]:
        old.unlink()
    return backup
