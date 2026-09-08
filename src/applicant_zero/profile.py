from dataclasses import dataclass


@dataclass(frozen=True)
class CandidateProfile:
    locations: tuple[str, ...]
    role_families: dict[str, tuple[str, ...]]
    skills: tuple[str, ...]


RISHI_PROFILE = CandidateProfile(
    locations=("sydney", "hybrid", "remote"),
    role_families={
        "data_bi": ("data analyst", "reporting analyst", "analytics analyst"),
        "power_bi": ("business intelligence", "power bi", "bi analyst"),
        "business_analysis": ("business analyst", "systems analyst", "business systems"),
    },
    skills=(
        "power bi", "dax", "power query", "microsoft fabric", "semantic model",
        "sql", "python", "pandas", "tableau", "excel", "data quality",
        "data modelling", "requirements", "process mapping", "gap analysis",
        "stakeholder", "business requirements", "data migration", "jira",
    ),
)
