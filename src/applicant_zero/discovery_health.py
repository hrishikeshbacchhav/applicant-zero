"""Read the newest private discovery log without exposing job or profile data."""

from pathlib import Path
from datetime import datetime, timedelta


def discovery_log_status(project_root: Path, stale_after_hours: int = 30) -> tuple[bool, str]:
    logs = project_root / "logs"
    candidates = sorted(logs.glob("refresh_*.log"), key=lambda item: item.stat().st_mtime, reverse=True) if logs.exists() else []
    if not candidates:
        return False, "No private discovery refresh log has been recorded yet."
    latest = candidates[0]
    if datetime.now() - datetime.fromtimestamp(latest.stat().st_mtime) > timedelta(hours=stale_after_hours):
        return False, f"Latest refresh log is stale: {latest.name}. Run a refresh or check the Windows task schedule."
    text = latest.read_text(encoding="utf-8", errors="replace")[-4_000:]
    if "finished successfully" in text:
        return True, f"Latest refresh log completed successfully: {latest.name}."
    if "discovery refresh failed" in text.lower():
        return False, f"Latest refresh log reported a failure: {latest.name}."
    return False, f"Latest refresh log did not record completion: {latest.name}."
