"""Versioned domain contracts shared by discovery, drafting and application flows."""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum


class FactClass(StrEnum):
    REUSABLE = "reusable"
    SUPPORTED = "supported"
    UNKNOWN = "unknown"
    PROTECTED = "protected"


class ActionKind(StrEnum):
    CAPTCHA = "captcha"
    ACCOUNT = "account"
    VERIFICATION = "verification"
    PROTECTED_ANSWER = "protected_answer"
    UNKNOWN_QUESTION = "unknown_question"
    FINAL_SUBMISSION = "final_submission"
    UNSUPPORTED_ROUTE = "unsupported_route"


@dataclass(frozen=True)
class CandidateFact:
    key: str
    value: str
    fact_class: FactClass
    source: str
    updated_at: str

    @property
    def usable_for_ordinary_field(self) -> bool:
        return bool(self.value) and self.fact_class is FactClass.REUSABLE


@dataclass(frozen=True)
class ManualAction:
    external_id: str
    kind: ActionKind
    title: str
    detail: str
    status: str = "Open"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["kind"] = self.kind.value
        return data


@dataclass(frozen=True)
class DiscoveryRecord:
    external_id: str
    title: str
    company: str
    location: str
    source: str
    url: str
    description: str
    lane: str | None
    first_seen_at: str
    last_seen_at: str
