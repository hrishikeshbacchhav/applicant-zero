"""Explicit, private eligibility checks for role preparation.

The module deliberately distinguishes a listing requirement from an answer to
an employer form.  It can prevent an obviously incompatible route from being
prepared, but does not guess protected information or submit a declaration.
"""

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class EligibilityCheck:
    outcome: str
    requirements: tuple[str, ...]
    detail: str


_RULES = (
    (r"(?:must be|only)\s+(?:an\s+)?australian citizen|australian citizenship(?:\s+and|\s+is|\s+required)", "Australian citizenship required", "citizenship"),
    (r"(?:citizen|citizenship)\s+or\s+(?:permanent resident|permanent residency)", "Australian citizenship or permanent residency required", "residency"),
    (r"permanent resident(?:s|cy)?\s+(?:only|required)", "Australian permanent residency required", "residency"),
    (r"(?:baseline|nv1|nv2|negative vetting|security)\s+clearance", "security clearance requirement", "clearance"),
    (r"(?:unrestricted|full)\s+(?:working|work)\s+rights", "unrestricted work-rights requirement", "work_rights"),
    (r"(?:no|without)\s+(?:visa\s+)?sponsorship", "no-sponsorship requirement", "sponsorship"),
)


def listing_eligibility_requirements(description: str) -> tuple[tuple[str, str], ...]:
    text = description.casefold()
    found: list[tuple[str, str]] = []
    for pattern, label, kind in _RULES:
        if re.search(pattern, text) and (label, kind) not in found:
            found.append((label, kind))
    return tuple(found)


def evaluate_listing_eligibility(description: str, profile: dict) -> EligibilityCheck:
    """Return a conservative preparation decision based on explicit text.

    ``blocked`` is reserved for a direct citizenship/residency condition that
    conflicts with a confirmed profile value. Everything else remains a
    candidate confirmation rather than an inferred application answer.
    """
    requirements = listing_eligibility_requirements(description)
    if not requirements:
        return EligibilityCheck("clear", (), "No specific eligibility condition was detected in the imported listing.")
    eligibility = profile.get("eligibility", {}) if isinstance(profile, dict) else {}
    citizenship = str(eligibility.get("citizenship_status", "")).casefold()
    visa_type = str(eligibility.get("visa_type", "")).casefold()
    labels = tuple(label for label, _ in requirements)
    citizenship_or_residency = any(kind in {"citizenship", "residency"} for _, kind in requirements)
    if citizenship_or_residency and citizenship and not any(word in citizenship for word in ("citizen", "permanent resident")):
        return EligibilityCheck("blocked", labels, "The listing requires citizenship or residency that conflicts with the confirmed private profile. Keep this role out of application preparation.")
    if citizenship_or_residency and "subclass 500" in visa_type:
        return EligibilityCheck("blocked", labels, "The listing requires citizenship or residency and the confirmed private profile records a student visa. Keep this role out of application preparation.")
    return EligibilityCheck("confirm", labels, "This listing has eligibility or clearance conditions. Confirm the exact employer wording in the form before continuing.")
