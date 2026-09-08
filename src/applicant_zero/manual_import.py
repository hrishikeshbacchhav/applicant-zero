"""Bring a listing the candidate found into the same local review workflow."""

from hashlib import sha256
from urllib.parse import urlsplit

from .profile import CandidateProfile
from .scoring import Job, score_job
from .storage import log_application_event, save_match


def source_name(url: str) -> str:
    host = urlsplit(url).netloc.lower().removeprefix("www.")
    if "seek." in host:
        return "Imported · SEEK"
    if "linkedin." in host:
        return "Imported · LinkedIn"
    if "indeed." in host:
        return "Imported · Indeed"
    if host:
        return f"Imported · {host}"
    return "Imported listing"


def import_listing(
    connection,
    profile: CandidateProfile,
    *,
    title: str,
    company: str,
    location: str,
    url: str,
    description: str,
) -> Job:
    """Validate and save a candidate-supplied public listing without scraping it."""
    clean = {
        "title": title.strip(),
        "company": company.strip(),
        "location": location.strip() or "Sydney, NSW",
        "url": url.strip(),
        "description": description.strip(),
    }
    if not all(clean.values()):
        raise ValueError("Add the role, company, link and job description before importing.")
    parsed = urlsplit(clean["url"])
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Use the full job-listing link, starting with https://.")
    if len(clean["description"]) < 80:
        raise ValueError("Paste enough of the job description to assess the role accurately.")
    if len(clean["description"]) > 30_000:
        raise ValueError("The job description is too long. Paste the role summary and requirements instead.")
    external_id = "manual:" + sha256(clean["url"].encode("utf-8")).hexdigest()[:20]
    job = Job(
        external_id=external_id,
        source=source_name(clean["url"]),
        **clean,
    )
    result = score_job(job, profile)
    save_match(connection, job, result)
    log_application_event(
        connection,
        job.external_id,
        "import",
        "completed",
        "Listing was imported from a link supplied by the candidate; no site was scraped.",
    )
    return job
