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
            "insight analyst", "decision support analyst", "data integrity analyst", "data assurance analyst", "data migration analyst",
            "data conversion analyst", "data reconciliation analyst", "data enablement analyst", "analytics specialist",
        ),
        "power_bi": ("business intelligence", "power bi", "bi analyst", "bi developer"),
        "business_analysis": ("business analyst", "process analyst", "systems analyst", "business systems", "technology business analyst", "business process analyst", "business improvement analyst", "change analyst", "technical business analyst", "digital business analyst", "business change analyst", "business solution analyst", "requirements analyst", "workflow analyst", "systems and process analyst", "process improvement analyst", "implementation analyst"),
        "adjacent_analytics": (
            "commercial analyst", "pricing analyst", "operations analyst",
            "finance operations analyst", "crm analyst", "insights analyst",
            "workforce analyst", "product analyst", "data insights analyst",
            "customer insights analyst", "performance analyst",
        ),
        "it_support": (
            "service desk", "help desk", "it support", "technical support", "desktop support", "application support",
            "support analyst", "it operations", "technology support", "ict support", "end user support",
            "it support specialist", "it support analyst", "support engineer", "customer support engineer", "technical customer support",
            "service desk technician", "field support technician", "it service management analyst", "it service desk officer",
            "it support administrator", "workplace technology support", "endpoint support", "device support", "business applications support", "software support analyst",
        ),
        "it_general": (
            "junior systems administrator", "systems administrator", "cloud support", "cyber security analyst", "cybersecurity analyst",
            "security operations", "qa analyst", "test analyst", "software tester", "network support", "implementation support",
            "junior developer", "graduate developer", "graduate technology", "technology graduate", "junior infrastructure", "cloud operations",
            "information security analyst", "soc analyst", "security analyst", "technical analyst", "implementation specialist",
            "software quality analyst", "qa engineer", "test engineer", "junior network engineer", "it project support",
        ),
        "administration": (
            "administration officer", "administration coordinator", "project administrator", "customer service administrator",
            "office administrator", "administrative assistant", "administration assistant", "administrative officer", "administration clerk", "data entry", "clerical officer", "program administrator", "reception and administration",
            "administrative coordinator", "customer operations administrator", "office coordinator", "operations administrator", "operations coordinator", "business support officer", "team coordinator", "administration support", "business administrator", "client services administrator", "project support officer", "administrative services officer", "program support officer", "office support coordinator", "business services officer",
        ),
    },
    skills=(
        "power bi", "dax", "power query", "microsoft fabric", "semantic model",
        "sql", "python", "pandas", "tableau", "excel", "data quality",
        "data modelling", "requirements", "process mapping", "gap analysis",
        "stakeholder", "business requirements", "data migration", "jira",
    ),
)
