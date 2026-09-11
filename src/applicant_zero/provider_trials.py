"""Evaluate a licensed job-data sample before connecting it to discovery."""

import json
from pathlib import Path

from .discovery_measurements import canonical_listing_key
from .scoring import Job


class ProviderTrialError(ValueError):
    pass


def load_trial_sample(path: Path, provider_name: str) -> list[Job]:
    """Load a local JSON sample; this never sends credentials or requests data."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProviderTrialError(f"Could not read the trial sample: {error}") from error
    rows = payload.get("jobs", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ProviderTrialError("Trial sample must be a JSON list or an object with a jobs list.")
    jobs: list[Job] = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        title, company = str(row.get("title", "")).strip(), str(row.get("company", row.get("company_name", ""))).strip()
        url = str(row.get("url", row.get("apply_url", ""))).strip()
        if not title or not company or not url:
            continue
        identifier = str(row.get("id", row.get("external_id", index))).strip()
        jobs.append(Job(
            external_id=f"trial:{provider_name}:{identifier}", title=title, company=company,
            location=str(row.get("location", "Unknown location")), source=f"Trial · {provider_name}",
            url=url, description=str(row.get("description", "")),
        ))
    return jobs


def assess_trial_sample(jobs: list[Job], existing_jobs: list[dict]) -> dict:
    """Return novelty figures so paid/provider choices are evidence-led."""
    existing = {
        canonical_listing_key(Job("existing", str(row["title"]), str(row["company"]), str(row["location"]), "Existing", "", ""))
        for row in existing_jobs
    }
    keys = [canonical_listing_key(job) for job in jobs]
    novel = [key for key in keys if key not in existing]
    return {
        "received": len(jobs),
        "valid_distinct": len(set(keys)),
        "new_to_current_database": len(set(novel)),
        "duplicates_in_sample": len(keys) - len(set(keys)),
        "overlaps_current_database": len(keys) - len(novel),
    }
