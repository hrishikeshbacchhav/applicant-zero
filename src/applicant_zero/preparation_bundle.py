"""Create the non-generative, local materials needed to prepare one role."""

from dataclasses import dataclass
from pathlib import Path

from .application_session import create_session_plan
from .material_manifest import create_material_manifest
from .packets import create_application_packet
from .resume_output import create_editable_resume_copy


@dataclass(frozen=True)
class PreparationBundle:
    """Local files created for a role, plus an optional Word-copy issue."""

    manifest: Path
    packet: Path
    session_plan: Path
    editable_resume_copy: Path | None
    editable_resume_issue: str = ""


def create_preparation_bundle(database_path: Path, external_id: str) -> PreparationBundle:
    """Create safe local preparation materials without calling an AI or employer site.

    A missing Word master must not prevent the evidence manifest, packet and
    session plan from being useful, so its error is reported separately.
    """
    manifest = create_material_manifest(database_path, external_id)
    packet = create_application_packet(database_path, external_id)
    session_plan = create_session_plan(database_path, external_id)
    try:
        editable_resume_copy = create_editable_resume_copy(database_path, external_id)
    except ValueError as error:
        return PreparationBundle(manifest, packet, session_plan, None, str(error))
    return PreparationBundle(manifest, packet, session_plan, editable_resume_copy)
