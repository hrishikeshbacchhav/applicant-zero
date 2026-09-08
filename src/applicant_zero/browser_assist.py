import re
import sqlite3
import threading
import time
from pathlib import Path

from .application_answers import ensure_answer_library, salary_expectation_for_job
from .application_routes import classify_application_url
from .private_profile import load_profile
from .storage import get_match, log_application_event, update_workflow


_running: set[str] = set()
_running_lock = threading.Lock()


def browser_setup_issue() -> str:
    try:
        import playwright.sync_api  # noqa: F401
    except ModuleNotFoundError:
        return 'Browser assistance needs the free Playwright package. Run: python -m pip install -e ".[browser]"'
    return ""


def _log(database_path: Path, external_id: str, status: str, detail: str) -> None:
    with sqlite3.connect(database_path) as connection:
        log_application_event(connection, external_id, "browser_assist", status, detail)


def _descriptor(element) -> str:
    values = []
    for attribute in ("name", "id", "placeholder", "aria-label", "autocomplete"):
        value = element.get_attribute(attribute)
        if value:
            values.append(value)
    return " ".join(values).lower()


def _choose_select_option(element, descriptor: str, salary_expectation: str, referral_source: str) -> bool:
    """Choose only the two reusable dropdown answers we can identify safely."""
    if re.search(r"visa|sponsor|work.?rights|citizen|gender|race|ethnic|disab|medical|injury|birth|veteran", descriptor):
        return False
    if re.search(r"salary|compensation|remuneration", descriptor):
        target_match = re.search(r"(\d{2,3}(?:,\d{3})?)", salary_expectation)
        target = int(target_match.group(1).replace(",", "")) if target_match else 0
        if not target:
            return False
        best: tuple[int, str] | None = None
        options = element.locator("option")
        for index in range(options.count()):
            option = options.nth(index)
            label = option.inner_text().strip()
            value = option.get_attribute("value")
            figures = [int(number.replace(",", "")) * (1_000 if "k" in label.lower() else 1) for number in re.findall(r"\d{2,3}(?:,\d{3})?", label)]
            if not value or not figures:
                continue
            midpoint = sum(figures[:2]) // len(figures[:2])
            candidate = (abs(midpoint - target), value)
            if best is None or candidate < best:
                best = candidate
        if best:
            element.select_option(best[1])
            return True
    if re.search(r"hear.*role|hear.*job|referral.?source|how.*hear", descriptor) and referral_source:
        preferred = referral_source.lower()
        options = element.locator("option")
        for index in range(options.count()):
            option = options.nth(index)
            label = option.inner_text().strip().lower()
            value = option.get_attribute("value")
            if value and (preferred in label or label in preferred or "company" in label and "website" in label):
                element.select_option(value)
                return True
    return False


def _prefill_page(page, job: dict, profile: dict, answers: dict) -> tuple[int, int]:
    verified = answers["verified_answers"]
    full_name = str(verified.get("full_name", "")).strip()
    name_parts = full_name.split()
    first_name = name_parts[0] if name_parts else ""
    last_name = name_parts[-1] if len(name_parts) > 1 else ""
    resume_path = profile.get("resumes", {}).get(job.get("resume_family"), "")
    salary_expectation = salary_expectation_for_job(job, answers)
    protected_or_uncertain = re.compile(
        r"visa|sponsor|work.?rights|citizen|gender|race|ethnic|disab|medical|injury|birth|veteran|password"
    )
    fields = page.locator("input, textarea")
    filled = 0
    resume_attached = False
    for index in range(fields.count()):
        element = fields.nth(index)
        try:
            input_type = (element.get_attribute("type") or "text").lower()
            descriptor = _descriptor(element)
            if input_type == "file":
                if element.is_enabled() and not resume_attached and resume_path and Path(resume_path).exists() and "cover" not in descriptor:
                    element.set_input_files(resume_path)
                    resume_attached = True
                    filled += 1
                continue
            if not element.is_visible() or not element.is_enabled():
                continue
            if input_type not in {"text", "email", "tel", "url", "search"} and element.evaluate("node => node.tagName.toLowerCase()") != "textarea":
                continue
            if protected_or_uncertain.search(descriptor):
                continue
            value = ""
            if re.search(r"first.?name|given.?name", descriptor):
                value = first_name
            elif re.search(r"last.?name|family.?name|surname", descriptor):
                value = last_name
            elif re.search(r"full.?name|candidate.?name", descriptor) or descriptor.strip() == "name":
                value = full_name
            elif "email" in descriptor:
                value = str(verified.get("email", ""))
            elif re.search(r"phone|mobile|telephone|tel", descriptor):
                value = str(verified.get("phone", ""))
            elif re.search(r"location|city", descriptor):
                value = str(verified.get("current_location", ""))
            elif re.search(r"available|start.?date", descriptor):
                value = str(verified.get("available_from", ""))
            elif re.search(r"salary|compensation|remuneration", descriptor):
                value = salary_expectation
            elif re.search(r"notice.?period", descriptor):
                value = str(answers["answers_requiring_confirmation"].get("notice_period", ""))
            elif "linkedin" in descriptor:
                value = str(answers["answers_requiring_confirmation"].get("linkedin_url", ""))
            elif re.search(r"portfolio|website", descriptor):
                value = str(answers["answers_requiring_confirmation"].get("portfolio_url", ""))
            elif re.search(r"hear.*role|hear.*job|referral.?source", descriptor):
                value = str(answers["answers_requiring_confirmation"].get("referral_source", ""))
            if value and not element.input_value().strip():
                element.fill(value)
                filled += 1
        except Exception:
            continue

    selects = page.locator("select")
    for index in range(selects.count()):
        element = selects.nth(index)
        try:
            if element.is_visible() and element.is_enabled() and not element.input_value():
                if _choose_select_option(
                    element,
                    _descriptor(element),
                    salary_expectation,
                    str(answers["answers_requiring_confirmation"].get("referral_source", "")),
                ):
                    filled += 1
        except Exception:
            continue

    unresolved = 0
    required = page.locator("input[required], textarea[required], select[required], [aria-required='true']")
    for index in range(required.count()):
        element = required.nth(index)
        try:
            if not element.is_visible():
                continue
            tag = element.evaluate("node => node.tagName.toLowerCase()")
            input_type = (element.get_attribute("type") or "").lower()
            if input_type in {"checkbox", "radio"}:
                complete = element.is_checked()
            elif tag == "select":
                complete = bool(element.input_value())
            else:
                complete = bool(element.input_value().strip())
            if not complete:
                unresolved += 1
                element.evaluate("node => { node.style.outline = '3px solid #d97706'; node.style.outlineOffset = '2px'; }")
        except Exception:
            continue
    return filled, unresolved


def run_browser_assistant(database_path: Path, external_id: str) -> None:
    try:
        setup_issue = browser_setup_issue()
        if setup_issue:
            _log(database_path, external_id, "setup_needed", setup_issue)
            return
        with sqlite3.connect(database_path) as connection:
            job = get_match(connection, external_id)
        if job is None:
            _log(database_path, external_id, "error", "Job was not found in the local database.")
            return
        project_root = database_path.parent.parent
        profile = load_profile(project_root / "private" / "candidate_profile.json")
        if not profile:
            _log(database_path, external_id, "error", "Private candidate profile is not ready.")
            return
        answers = ensure_answer_library(project_root, profile)
        route = classify_application_url(job["url"])
        if route.support_level not in {"assisted", "pilot"}:
            _log(database_path, external_id, "manual_review", route.detail)
            return

        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright

        browser_profile = project_root / "private" / "browser_profile"
        browser_profile.mkdir(parents=True, exist_ok=True)
        _log(database_path, external_id, "starting", f"Opening {route.platform} application in the assisted browser.")
        with sync_playwright() as playwright:
            try:
                context = playwright.chromium.launch_persistent_context(
                    str(browser_profile), channel="chrome", headless=False
                )
            except PlaywrightError:
                context = playwright.chromium.launch_persistent_context(
                    str(browser_profile), headless=False
                )
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(route.apply_url, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(2_000)
            filled, unresolved = _prefill_page(page, job, profile, answers)
            _log(
                database_path,
                external_id,
                "ready_for_review",
                f"Filled {filled} safe fields. {unresolved} required fields remain highlighted for review. Final submission was not clicked.",
            )
            if job["workflow_status"] in {"New", "Saved"}:
                with sqlite3.connect(database_path) as connection:
                    update_workflow(connection, external_id, "Preparing", job["notes"])
            while context.pages:
                time.sleep(1)
            _log(database_path, external_id, "closed", "The assisted browser was closed without Applicant Zero clicking submit.")
    except Exception as error:
        _log(database_path, external_id, "error", f"Browser assistance stopped: {type(error).__name__}: {error}")
    finally:
        with _running_lock:
            _running.discard(external_id)


def start_browser_assistant(database_path: Path, external_id: str) -> bool:
    with _running_lock:
        if external_id in _running:
            return False
        _running.add(external_id)
    _log(database_path, external_id, "queued", "Browser assistance was requested from the dashboard.")
    thread = threading.Thread(
        target=run_browser_assistant,
        args=(database_path, external_id),
        daemon=True,
        name=f"applicant-zero-{external_id[:12]}",
    )
    thread.start()
    return True
