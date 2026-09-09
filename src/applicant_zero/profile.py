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
        ),
        "power_bi": ("business intelligence", "power bi", "bi analyst"),
        "business_analysis": ("business analyst", "process analyst", "systems analyst", "business systems"),
        "adjacent_analytics": (
            "commercial analyst", "pricing analyst", "operations analyst",
            "finance operations analyst", "crm analyst", "insights analyst",
            "workforce analyst", "product analyst", "data insights analyst",
        ),
        "it_support": (
            "service desk", "help desk", "it support", "technical support", "desktop support", "application support",
            "support analyst", "it operations", "technology support",
        ),
    },
    skills=(
        "power bi", "dax", "power query", "microsoft fabric", "semantic model",
        "sql", "python", "pandas", "tableau", "excel", "data quality",
        "data modelling", "requirements", "process mapping", "gap analysis",
        "stakeholder", "business requirements", "data migration", "jira",
    ),
)
