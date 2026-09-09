"""A private, versioned candidate fact library derived from confirmed profile data."""

import json
from datetime import datetime
from pathlib import Path

from .contracts import CandidateFact, FactClass


FACT_LIBRARY_VERSION = 1


def _value(section: dict, key: str) -> str:
    return str(section.get(key, "")).strip()


def _fact(key: str, value: str, fact_class: FactClass, source: str) -> CandidateFact:
    return CandidateFact(key, value, fact_class, source, datetime.now().isoformat(timespec="seconds"))


def build_fact_library(profile: dict, answer_library: dict | None = None) -> list[CandidateFact]:
    """Translate a candidate profile into facts that later workers can classify safely."""
    contact = profile.get("contact", {})
    availability = profile.get("availability", {})
    eligibility = profile.get("eligibility", {})
    identity = profile.get("identity", {})
    confirmed = (answer_library or {}).get("answers_requiring_confirmation", {})
    facts = [
        _fact("full_name", _value(contact, "legal_name"), FactClass.REUSABLE, "candidate_profile"),
        _fact("email", _value(contact, "email"), FactClass.REUSABLE, "candidate_profile"),
        _fact("phone", _value(contact, "phone"), FactClass.REUSABLE, "candidate_profile"),
        _fact("current_location", _value(contact, "current_location"), FactClass.REUSABLE, "candidate_profile"),
        _fact("address", _value(contact, "address"), FactClass.REUSABLE, "candidate_profile"),
        _fact("available_from", _value(availability, "full_time_from"), FactClass.REUSABLE, "candidate_profile"),
        _fact("linkedin_url", _value(confirmed, "linkedin_url"), FactClass.REUSABLE, "confirmed_answers"),
        _fact("notice_period", _value(confirmed, "notice_period"), FactClass.REUSABLE, "confirmed_answers"),
        _fact("referral_source", _value(confirmed, "referral_source"), FactClass.REUSABLE, "confirmed_answers"),
        _fact("pronouns", _value(identity, "pronouns"), FactClass.REUSABLE, "candidate_profile"),
        _fact("work_rights", _value(eligibility, "current_work_rights"), FactClass.PROTECTED, "candidate_profile"),
        _fact("requires_sponsorship", _value(eligibility, "requires_sponsorship_answer"), FactClass.PROTECTED, "candidate_profile"),
        _fact("visa_type", _value(eligibility, "visa_type"), FactClass.PROTECTED, "candidate_profile"),
        _fact("citizenship_status", _value(eligibility, "citizenship_status"), FactClass.PROTECTED, "candidate_profile"),
        _fact("ethnicity", _value(identity, "ethnicity"), FactClass.PROTECTED, "candidate_profile"),
    ]
    return facts


def ensure_fact_library(state_root: Path, profile: dict, answer_library: dict | None = None) -> dict:
    """Write a portable, auditable fact snapshot in private runtime state."""
    path = state_root / "private" / "candidate_facts.json"
    payload = {
        "schema_version": FACT_LIBRARY_VERSION,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "facts": [
            {
                "key": fact.key,
                "value": fact.value,
                "class": fact.fact_class.value,
                "source": fact.source,
                "updated_at": fact.updated_at,
            }
            for fact in build_fact_library(profile, answer_library)
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload
