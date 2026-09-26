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
    RoleLane("data_bi", "Data, analytics and business intelligence", 1, ("data analyst", "data reporting", "business intelligence", "bi analyst", "bi developer", "power bi", "reporting analyst", "reporting officer", "analytics analyst", "analytics officer", "data insights", "insights officer", "data specialist", "data officer", "data quality", "data governance", "data visualisation", "dashboard developer", "information analyst", "information management", "master data analyst", "analytics consultant"), "data_bi"),
    RoleLane("business_analysis", "Business, systems and process analysis", 2, ("business analyst", "business process", "process analyst", "systems analyst", "business systems", "technology business", "business operations analyst", "functional analyst", "operations excellence", "business improvement", "continuous improvement analyst", "business transformation analyst", "change analyst", "product analyst"), "business_analysis"),
    RoleLane("commercial_analytics", "Commercial, finance and performance analytics", 3, ("commercial analyst", "commercial operations analyst", "pricing analyst", "finance analyst", "revenue analyst", "performance analyst", "planning analyst", "workforce analyst", "workforce planning", "sales operations analyst", "customer insights"), "data_bi"),
    RoleLane("data_operations", "Data and CRM operations", 4, ("data administrator", "data coordinator", "data operations", "master data", "crm analyst", "crm administrator", "data governance", "reporting support", "data management"), "data_bi"),
    RoleLane("it_support", "IT and service support", 5, ("service desk", "technical service desk", "help desk", "it support", "it support coordinator", "it technician", "ict support", "application support", "technical support", "technology support", "systems support", "desktop support", "end user support", "it service delivery", "it operations", "it graduate"), "it_support"),
    RoleLane("it_general", "Broader entry-level IT", 6, ("junior systems administrator", "junior infrastructure", "junior systems engineer", "systems administrator", "cloud support", "cloud operations", "cyber security analyst", "cybersecurity analyst", "security operations", "qa analyst", "test analyst", "software tester", "network support", "implementation support", "technology implementation", "it implementation", "technology analyst", "junior it", "junior developer", "graduate developer", "graduate technology", "technology graduate"), "it_general"),
    RoleLane("administration", "Full-time administration", 7, ("administration officer", "administrative officer", "administration coordinator", "administrative coordinator", "project administrator", "customer service administrator", "customer operations administrator", "office administrator", "office coordinator", "operations administrator", "operations coordinator", "business support officer", "administrative assistant", "administration assistant", "administration clerk", "data entry", "clerical officer", "program administrator", "team coordinator", "reception and administration"), "administration"),
)


@dataclass(frozen=True)
class SourceContract:
    identifier: str
    label: str
    acquisition: str
    frequency: str
    application_route: str


SOURCE_CONTRACTS = (
    SourceContract("lever", "Lever", "public ATS job feed", "weekday, several checks", "prepare and open listing"),
    SourceContract("greenhouse", "Greenhouse", "public ATS job feed", "weekday, several checks", "prepare and open listing"),
    SourceContract("ashby", "Ashby", "public ATS job feed", "weekday, several checks", "prepare and open listing"),
    SourceContract("smartrecruiters", "SmartRecruiters", "public ATS job feed", "weekday, several checks", "prepare and open listing"),
    SourceContract("workable", "Workable", "public ATS job feed", "weekday, several checks", "prepare and open listing"),
    SourceContract("recruitee", "Recruitee", "transitional public ATS job feed", "weekday, several checks", "prepare and open listing"),
    SourceContract("workday", "Workday", "public ATS job feed", "weekday, several checks", "prepare and open listing"),
    SourceContract("adzuna", "Permitted broad job feed", "configured API", "daily", "prepare and open listing"),
    SourceContract("jobicy", "Jobicy remote jobs", "public attributed API", "daily", "open the Jobicy listing"),
    SourceContract("remotive", "Remotive remote jobs", "public attributed API", "daily", "open the Remotive listing"),
    SourceContract("himalayas", "Himalayas remote jobs", "public attributed API", "daily", "open the Himalayas listing"),
    SourceContract("seek", "SEEK", "manual link/import", "candidate initiated", "prepare and open listing"),
    SourceContract("linkedin", "LinkedIn", "manual link/import", "candidate initiated", "prepare and open listing"),
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
