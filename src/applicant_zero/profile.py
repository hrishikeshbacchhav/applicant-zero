from dataclasses import dataclass


@dataclass(frozen=True)
class CandidateProfile:
    locations: tuple[str, ...]
    role_families: dict[str, tuple[str, ...]]
    skills: tuple[str, ...]


RISHI_PROFILE = CandidateProfile(
    locations=("sydney", "hybrid", "remote"),
    role_families={
        "data_bi": (
            "data analyst", "reporting analyst", "analytics analyst", "data and insights analyst", "data & insights analyst",
            "data quality analyst", "data governance analyst", "information analyst", "insights analyst", "performance analyst",
            "data reporting analyst", "data management analyst", "data visualisation analyst", "information management analyst", "master data analyst",
        ),
        "power_bi": ("business intelligence", "power bi", "bi analyst", "bi developer"),
        "business_analysis": ("business analyst", "process analyst", "systems analyst", "business systems", "technology business analyst", "business process analyst", "business improvement analyst", "change analyst"),
        "adjacent_analytics": (
            "commercial analyst", "pricing analyst", "operations analyst",
            "finance operations analyst", "crm analyst", "insights analyst",
            "workforce analyst", "product analyst", "data insights analyst",
            "customer insights analyst", "performance analyst",
        ),
        "it_support": (
            "service desk", "help desk", "it support", "technical support", "desktop support", "application support",
            "support analyst", "it operations", "technology support", "ict support", "end user support",
        ),
        "it_general": (
            "junior systems administrator", "systems administrator", "cloud support", "cyber security analyst", "cybersecurity analyst",
            "security operations", "qa analyst", "test analyst", "software tester", "network support", "implementation support",
            "junior developer", "graduate developer", "graduate technology", "technology graduate", "junior infrastructure", "cloud operations",
        ),
        "administration": (
            "administration officer", "administration coordinator", "project administrator", "customer service administrator",
            "office administrator", "administrative assistant", "administration assistant", "administrative officer", "administration clerk", "data entry", "clerical officer", "program administrator", "reception and administration",
        ),
    },
    skills=(
        "power bi", "dax", "power query", "microsoft fabric", "semantic model",
        "sql", "python", "pandas", "tableau", "excel", "data quality",
        "data modelling", "requirements", "process mapping", "gap analysis",
        "stakeholder", "business requirements", "data migration", "jira",
    ),
)
