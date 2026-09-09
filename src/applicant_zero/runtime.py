"""Private runtime state kept outside the source checkout and cloud-sync folders."""

import os
import shutil
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


def backup_database(repository_root: Path, reason: str = "startup") -> Path | None:
    """Make a dated raw backup before a run; keeps the latest seven per reason."""
    database = database_path(repository_root)
    if not database.exists() or database.stat().st_size == 0:
        return None
    backup_dir = database.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = backup_dir / f"applicant_zero-{reason}-{stamp}.sqlite3"
    shutil.copy2(database, backup)
    retained = sorted(backup_dir.glob(f"applicant_zero-{reason}-*.sqlite3"), key=lambda item: item.stat().st_mtime, reverse=True)
    for old in retained[7:]:
        old.unlink()
    return backup
