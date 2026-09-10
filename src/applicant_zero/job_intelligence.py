"""Extract transparent, reviewable details from an imported job description."""

import re
from dataclasses import dataclass

from .application_answers import advertised_salary_range


# A closing full stop or comma is common after an email address in a listing.
# It is punctuation, not part of the address, so do not reject it as a suffix.
EMAIL_PATTERN = re.compile(r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w-])", re.IGNORECASE)
CLOSING_PATTERN = re.compile(
    r"(?:applications?\s+(?:close|closing|must\s+be\s+received(?:\s+by)?)|apply\s+by|closing\s+date)\s*[:\-]?\s*([^\n.]{3,90})",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class JobIntelligence:
    salary: str
    contacts: tuple[str, ...]
    closing_detail: str
    employment_type: str
    location_signal: str


def inspect_job(title: str, location: str, description: str) -> JobIntelligence:
    text = description or ""
    salary_range = advertised_salary_range(text)
    salary = ""
    if salary_range:
        salary = f"AUD {salary_range[0]:,}–{salary_range[1]:,} base salary, where stated in the listing"
    contacts = tuple(dict.fromkeys(match.group(0) for match in EMAIL_PATTERN.finditer(text)))[:3]
    closing = CLOSING_PATTERN.search(text)
    closing_detail = " ".join(closing.group(1).split()) if closing else ""
    lowered = f"{title} {text}".lower()
    employment_type = "Full-time" if re.search(r"\bfull[ -]?time\b", lowered) else "Contract" if re.search(r"\b(?:fixed.term|contract)\b", lowered) else "Not stated"
    lowered_location = location.lower()
    if "sydney" in lowered_location:
        location_signal = "Sydney specified"
    elif "nsw" in lowered_location or "new south wales" in lowered_location:
        location_signal = "NSW only — confirm the workplace"
    elif "remote" in lowered_location or "hybrid" in lowered_location:
        location_signal = "Remote or hybrid"
    else:
        location_signal = "Check the listed workplace"
    return JobIntelligence(salary, contacts, closing_detail, employment_type, location_signal)
