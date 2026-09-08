import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from .private_profile import load_profile
from .storage import list_matches


def create_application_packet(database_path: Path, external_id: str) -> Path:
    with sqlite3.connect(database_path) as connection:
        rows = [row for row in list_matches(connection) if row["external_id"] == external_id]
    if not rows:
        raise ValueError("Job not found")
    row = rows[0]
    profile = load_profile(database_path.parent.parent / "private" / "candidate_profile.json")
    if not profile:
        raise ValueError("Private candidate profile is not ready")
    evidence = ", ".join(json.loads(row["matched_evidence"])) or "Review the original description manually."
    missing = ", ".join(json.loads(row["missing_requirements"])) or "No additional named requirement detected."
    reasons = "\n".join(f"- {reason}" for reason in json.loads(row["reasons"]))
    resume_path = profile["resumes"].get(row["resume_family"], "")
    content = f"""# Application preparation packet

Created: {datetime.now().strftime('%Y-%m-%d %H:%M')}

## Role

- **Title:** {row['title']}
- **Company:** {row['company']}
- **Location:** {row['location']}
- **Original listing:** {row['url']}
- **Current tracker status:** {row['workflow_status']}

## Approved application materials

- **Résumé family:** {row['resume_family'] or 'Not recommended'}
- **Résumé file:** {resume_path}
- **Full-time availability:** {profile['availability']['full_time_from']}

## Matching evidence

{evidence}

## Requirements to check

{missing}

## Why this role was surfaced

{reasons}

## Before submitting

- Read the original listing and confirm the role is still open.
- Tailor only truthful résumé wording to the role's stated requirements.
- Confirm each work-rights or sponsorship answer is accurate at the time of submission.
- Record the employer's confirmation only after you submit the application yourself.

## Imported job description

{row['description']}
"""
    packet_directory = database_path.parent.parent / "private" / "application_packets"
    packet_directory.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^a-z0-9]+", "-", f"{row['company']}-{row['title']}".lower()).strip("-")
    packet_path = packet_directory / f"{safe_name}.md"
    packet_path.write_text(content, encoding="utf-8")
    return packet_path
