"""Preserve structured public listing metadata in a reviewable text form."""

from __future__ import annotations

from typing import Any


def text(value: Any) -> str:
    """Return a compact public metadata value without inventing a value."""
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def append_listing_metadata(
    description: str, *, posted_at: Any = "", employment_type: Any = "", salary: Any = "",
) -> str:
    """Attach source-provided metadata to a listing description.

    The dashboard already persists descriptions across sources. Keeping provenance
    in the imported record avoids schema-specific assumptions while making the
    date, work arrangement and compensation visible in the preparation brief.
    Empty or absent fields are deliberately omitted.
    """
    details = []
    if text(posted_at):
        details.append(f"Published: {text(posted_at)}")
    if text(employment_type):
        details.append(f"Employment type: {text(employment_type)}")
    if text(salary):
        details.append(f"Compensation: {text(salary)}")
    if not details:
        return description or ""
    body = (description or "").strip()
    suffix = "Source metadata: " + "; ".join(details)
    return f"{body}\n{suffix}".strip()
