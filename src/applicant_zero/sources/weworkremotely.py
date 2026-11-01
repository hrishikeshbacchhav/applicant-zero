"""Read We Work Remotely's public attributed jobs RSS feed."""

import hashlib
import html
import re
from dataclasses import dataclass
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from ..scoring import Job
from .metadata import append_listing_metadata

RSS_URL = "https://weworkremotely.com/remote-jobs.rss"
CATEGORY_FEEDS = (
    "remote-customer-support-jobs",
    "remote-management-and-finance-jobs",
    "remote-programming-jobs",
    "remote-devops-sysadmin-jobs",
)


@dataclass(frozen=True)
class TargetedFetchReport:
    requests: int
    errors: tuple[str, ...] = ()


def _plain_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(value or ""))).strip()


def _location(title: str, description: str) -> str:
    text = f"{title} {description}".casefold()
    if "australia" in text:
        return "Remote, Australia"
    if any(term in text for term in ("worldwide", "anywhere in the world", "work from anywhere")):
        return "Remote, Worldwide"
    return "Remote, eligibility not supplied"


def _job_from_item(item: ElementTree.Element) -> Job:
    title = _plain_text(item.findtext("title") or "Untitled role")
    listing_url = (item.findtext("link") or item.findtext("guid") or "").strip()
    identifier = hashlib.sha256((listing_url or title).encode("utf-8")).hexdigest()[:24]
    description = _plain_text(item.findtext("description") or "")
    category = _plain_text(item.findtext("category") or "")
    if category:
        description = f"{description}\nCategory: {category}".strip()
    company = title.split(":", 1)[0].strip() if ":" in title else "Unknown company"
    return Job(
        external_id=f"weworkremotely:{identifier}", title=title, company=company or "Unknown company",
        location=_location(title, description), source="We Work Remotely", url=listing_url or RSS_URL,
        description=append_listing_metadata(description, posted_at=item.findtext("pubDate") or ""),
    )


def build_category_rss_url(category: str) -> str:
    """Return one explicitly published We Work Remotely category feed URL."""
    return f"https://weworkremotely.com/categories/{category.strip()}.rss"


def fetch_jobs(*, max_items: int = 100, rss_url: str = RSS_URL) -> list[Job]:
    """Read one public RSS document and keep a conservative local item cap."""
    request = Request(rss_url, headers={"Accept": "application/rss+xml, application/xml", "User-Agent": "Applicant-Zero/0.1 (private job discovery)"})
    with urlopen(request, timeout=20) as response:
        root = ElementTree.fromstring(response.read())
    return [_job_from_item(item) for item in root.findall("./channel/item")[:max(1, min(100, int(max_items)))]]


def fetch_targeted_jobs(*, categories: tuple[str, ...] = CATEGORY_FEEDS, max_items: int = 100) -> tuple[list[Job], TargetedFetchReport]:
    """Read four explicitly published role-category feeds once per day.

    These cover the candidate's IT support, entry IT and operations-adjacent
    lanes that may not appear in the all-jobs RSS document's newest entries.
    Each URL is publicly documented by We Work Remotely and keeps its original
    listing link and attribution.
    """
    selected = tuple(category for category in categories if category.strip())[:4]
    jobs: list[Job] = []
    errors: list[str] = []
    for category in selected:
        try:
            jobs.extend(fetch_jobs(max_items=max_items, rss_url=build_category_rss_url(category)))
        except (OSError, ValueError, ElementTree.ParseError) as error:
            errors.append(f"{category}: {error}")
    return jobs, TargetedFetchReport(requests=len(selected), errors=tuple(errors))
