"""Translate recognised application questions into the candidate's saved answers.

This module is deliberately deterministic. It recognises common field wording,
adapts salary to the actual HTML field type, and leaves unfamiliar questions
alone for the review queue.
"""

import re

from .application_answers import salary_expectation_for_job


def field_answer(descriptor: str, input_type: str, answers: dict, job: dict) -> str:
    """Return a saved answer for one recognised field, or an empty value."""
    text = descriptor.lower()
    verified = answers.get("verified_answers", {})
    confirmed = answers.get("answers_requiring_confirmation", {})
    full_name = str(verified.get("full_name", "")).strip()
    parts = full_name.split()
    if re.search(r"first.?name|given.?name", text):
        return parts[0] if parts else ""
    if re.search(r"last.?name|family.?name|surname", text):
        return parts[-1] if len(parts) > 1 else ""
    if re.search(r"full.?name|candidate.?name", text) or text.strip() == "name":
        return full_name
    if "email" in text:
        return str(verified.get("email", ""))
    if re.search(r"phone|mobile|telephone|tel", text):
        return str(verified.get("phone", ""))
    if re.search(r"post.?code|zip(?:.?code)?", text):
        return str(verified.get("postcode", ""))
    if re.search(r"state|province|territory", text):
        return str(verified.get("state", ""))
    if re.search(r"country|nation", text):
        return str(verified.get("country", ""))
    if re.search(r"street.?address|home.?address|address", text):
        return str(verified.get("address", ""))
    if re.search(r"location|city|suburb", text):
        return str(verified.get("current_location", ""))
    if re.search(r"available|start.?date", text):
        return str(verified.get("available_from", ""))
    if re.search(r"salary|compensation|remuneration", text):
        value = salary_expectation_for_job(job, answers)
        if input_type == "number":
            match = re.search(r"(\d{2,3}(?:,\d{3})?)", value)
            return match.group(1).replace(",", "") if match else ""
        return value
    if re.search(r"notice.?period", text):
        return str(confirmed.get("notice_period", ""))
    if "linkedin" in text:
        return str(confirmed.get("linkedin_url", ""))
    if re.search(r"portfolio|website", text):
        return str(confirmed.get("portfolio_url", ""))
    if re.search(r"hear.*role|hear.*job|referral.?source", text):
        return str(confirmed.get("referral_source", ""))
    # Eligibility and identity declarations need a candidate's direct review
    # in the exact employer form. They are intentionally never prefilled.
    if re.search(r"work.?rights|right.?work|authori[sz].*work|sponsor|visa|immigration|citizen|permanent.?residen|pronouns?|race|ethnic", text):
        return ""
    return ""


def select_value(options: list[tuple[str, str]], answer: str) -> str:
    """Pick an exact or safely equivalent HTML select option for a known answer."""
    answer = answer.strip().casefold()
    if not answer:
        return ""
    normalized = re.sub(r"[^a-z0-9]+", " ", answer).strip()
    yes = {"yes", "y", "true", "1"}
    no = {"no", "n", "false", "0"}
    for value, label in options:
        candidate = re.sub(r"[^a-z0-9]+", " ", label.casefold()).strip()
        if candidate == normalized or candidate in normalized or normalized in candidate:
            return value
        if normalized in yes and candidate in yes:
            return value
        if normalized in no and candidate in no:
            return value
    return ""


def option_matches(answer: str, value: str, label: str = "") -> bool:
    """Return whether a radio-style option is an exact safe match for an answer.

    Hosted forms frequently use radio inputs instead of ``select`` controls.
    Their HTML value is often ``yes``/``no`` while the visible wording sits in
    a nearby label, so normalise both representations through ``select_value``.
    """
    return bool(select_value([(value, label or value)], answer))
