"""Small, explainable measurements for a bounded discovery refresh."""

import re
from collections import defaultdict

from .scoring import Job


def canonical_listing_key(job: Job) -> str:
    """Return the shared source-overlap identity used across discovery.

    Source providers routinely differ on legal company suffixes and whether a
    Greater Sydney listing is labelled with a suburb or city.  Keep raw source
    records unchanged, but treat those forms as one likely syndicated listing
    for counts, source contribution and duplicate analysis.
    """
    def clean(value: object) -> str:
        return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()

    company = re.sub(r"\b(?:pty|ltd|limited|inc|llc|plc)\b", "", clean(job.company))
    company = re.sub(r"\s+", " ", company).strip()
    location = clean(job.location)
    greater_sydney = (
        "parramatta", "north sydney", "macquarie park", "chatswood", "barangaroo",
        "pyrmont", "surry hills", "redfern", "alexandria", "mascot", "st leonards",
        "ryde", "rhodes", "homebush", "olympic park", "strathfield", "burwood",
        "bankstown", "liverpool", "blacktown", "penrith", "castle hill", "baulkham hills",
        "bella vista", "milsons point", "circular quay", "botany", "waterloo",
    )
    if "sydney" in location or any(place in location for place in greater_sydney):
        location = "greater sydney"
    elif "remote" in location and "australia" in location:
        location = "remote australia"
    elif "nsw" in location or "new south wales" in location:
        location = "nsw"
    return "|".join((company, clean(job.title), location))


def canonical_unique_jobs(jobs: list[Job]) -> list[Job]:
    """Keep one representative per likely syndicated listing.

    Raw source records are retained in the inventory. This helper is only for
    honest user-facing counts, where the same role should appear once even if
    an ATS feed and a broad provider both returned it.
    """
    preferred: dict[str, Job] = {}
    for job in jobs:
        preferred.setdefault(canonical_listing_key(job), job)
    return list(preferred.values())


def measure_sources(
    jobs: list[Job],
    visible_external_ids: set[str],
    *,
    request_counts: dict[str, int] | None = None,
    failure_counts: dict[str, int] | None = None,
) -> list[dict]:
    """Measure contribution without hiding any underlying source provenance."""
    request_counts = request_counts or {}
    failure_counts = failure_counts or {}
    by_source: dict[str, list[Job]] = defaultdict(list)
    by_key: dict[str, set[str]] = defaultdict(set)
    for job in jobs:
        by_source[job.source].append(job)
        by_key[canonical_listing_key(job)].add(job.source)

    sources = set(by_source) | set(request_counts) | set(failure_counts)
    rows: list[dict] = []
    for source in sorted(sources):
        source_jobs = by_source.get(source, [])
        repeated = sum(1 for job in source_jobs if len(by_key[canonical_listing_key(job)]) > 1)
        distinct = len({canonical_listing_key(job) for job in source_jobs if len(by_key[canonical_listing_key(job)]) == 1})
        rows.append({
            "source": source,
            "collected_count": len(source_jobs),
            "relevant_count": sum(job.external_id in visible_external_ids for job in source_jobs),
            "distinct_count": distinct,
            "repeated_count": repeated,
            "request_count": request_counts.get(source, 0),
            "failure_count": failure_counts.get(source, 0),
        })
    return rows
