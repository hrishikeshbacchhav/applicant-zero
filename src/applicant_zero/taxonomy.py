"""Search lanes and discovery-source contracts for the Sydney job search."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RoleLane:
    identifier: str
    label: str
    priority: int
    terms: tuple[str, ...]
    resume_family: str


ROLE_LANES = (
    RoleLane("data_bi", "Data, analytics and business intelligence", 1, ("data analyst", "data reporting", "business intelligence", "bi analyst", "bi developer", "power bi", "reporting analyst", "analytics analyst", "data insights", "data quality", "analytics consultant"), "data_bi"),
    RoleLane("business_analysis", "Business, systems and process analysis", 2, ("business analyst", "business process", "process analyst", "systems analyst", "business systems", "technology business", "operations excellence", "product analyst"), "business_analysis"),
    RoleLane("commercial_analytics", "Commercial, finance and performance analytics", 3, ("commercial analyst", "pricing analyst", "finance analyst", "performance analyst", "workforce analyst", "workforce planning", "customer insights"), "data_bi"),
    RoleLane("data_operations", "Data and CRM operations", 4, ("data administrator", "data operations", "master data", "crm analyst", "data governance", "reporting support", "data management"), "data_bi"),
    RoleLane("it_support", "IT and service support", 5, ("service desk", "help desk", "it support", "application support", "technical support", "systems support", "desktop support", "it graduate"), "it_support"),
)


@dataclass(frozen=True)
class SourceContract:
    identifier: str
    label: str
    acquisition: str
    frequency: str
    application_route: str


SOURCE_CONTRACTS = (
    SourceContract("lever", "Lever", "public ATS job feed", "weekday, several checks", "browser-assisted pilot"),
    SourceContract("greenhouse", "Greenhouse", "public ATS job feed", "weekday, several checks", "browser-assisted pilot"),
    SourceContract("ashby", "Ashby", "public ATS job feed", "weekday, several checks", "browser-assisted pilot"),
    SourceContract("adzuna", "Permitted broad job feed", "configured API", "daily", "link or browser handoff"),
    SourceContract("seek", "SEEK", "manual link/import", "candidate initiated", "manual or supported handoff"),
    SourceContract("linkedin", "LinkedIn", "manual link/import", "candidate initiated", "manual or supported handoff"),
)


def classify_lane(title: str, description: str = "") -> RoleLane | None:
    # A title is the most reliable routing signal.  Description-only fallback
    # helps incomplete ATS listings without allowing an incidental keyword to
    # re-route a clearly named support or commercial role.
    title_matches = [lane for lane in ROLE_LANES if any(term in title.lower() for term in lane.terms)]
    if title_matches:
        return min(title_matches, key=lambda lane: lane.priority)
    matches = [lane for lane in ROLE_LANES if any(term in description.lower() for term in lane.terms)]
    return min(matches, key=lambda lane: lane.priority) if matches else None
