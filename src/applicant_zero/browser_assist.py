import re
import sqlite3
import threading
import time
from pathlib import Path

from .application_answers import ensure_answer_library
from .form_answers import field_answer, select_value
from .application_routes import classify_application_url, supports_supervised_browser_handoff
from .private_profile import load_profile
from .storage import get_match, log_application_event, save_manual_action, update_workflow


_running: set[str] = set()
_running_lock = threading.Lock()


def _captcha_present(page) -> bool:
    """Detect a CAPTCHA without attempting to solve, click, or bypass it."""
    try:
        return page.locator(
            "iframe[src*='recaptcha'], iframe[src*='hcaptcha'], .g-recaptcha, .h-captcha, [data-sitekey]"
        ).count() > 0
    except Exception:
        return False


def _next_step_button(page):
    """Return a normal progression control, never an application-submit control."""
    try:
        controls = page.locator("button, input[type='button'], input[type='submit']")
        for index in range(controls.count()):
            control = controls.nth(index)
            if not control.is_visible() or not control.is_enabled():
                continue
            label = " ".join(
                filter(
                    None,
                    [
                        control.inner_text().strip(),
                        control.get_attribute("value"),
                        control.get_attribute("aria-label"),
                    ],
                )
            ).lower()
            if re.search(r"\b(submit|apply now|send application|finish application)\b", label):
                continue
            if re.search(r"\b(next|continue|review application|save and continue)\b", label):
                return control
    except Exception:
        return None
    return None


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
    # Lever and similar application forms sometimes keep the useful field name
    # only in the visible label.  Use that nearby label solely for identifying
    # a safe, known answer; never to infer an answer.
    try:
        label_text = element.evaluate(
            """node => {
                const labels = [];
                if (node.id) {
                    const label = document.querySelector(`label[for="${CSS.escape(node.id)}"]`);
                    if (label) labels.push(label.innerText);
                }
                const wrapper = node.closest('label, [data-qa], .application-question, .field');
                if (wrapper) labels.push(wrapper.innerText);
                return labels.join(' ').slice(0, 500);
            }"""
        )
        if label_text:
            values.append(label_text)
    except Exception:
        pass
    return " ".join(values).lower()


def _choose_select_option(element, descriptor: str, answers: dict, job: dict) -> bool:
    """Select only a recognised option equivalent to the candidate's saved fact."""
    answer = field_answer(descriptor, "select", answers, job)
    if not answer:
        return False
    options = element.locator("option")
    choices = [
        (option.get_attribute("value") or "", option.inner_text().strip())
        for option in (options.nth(index) for index in range(options.count()))
    ]
    selected = select_value(choices, answer)
    if not selected:
        return False
    element.select_option(selected)
    return True


def _application_form_is_ready(page) -> bool:
    """Avoid credential pages; wait until the candidate has navigated to an application form."""
    try:
        if page.locator("input[type='password']").count():
            return False
        fields = page.locator("input, textarea, select")
        if fields.count() < 3:
            return False
        descriptors = []
        for index in range(min(fields.count(), 30)):
            element = fields.nth(index)
            if element.is_visible():
                descriptors.append(_descriptor(element))
        text = " ".join(descriptors)
        return bool(re.search(r"first.?name|given.?name|resume|cv|cover.?letter", text))
    except Exception:
        return False


def _wait_for_candidate_handoff(page, timeout_seconds: int = 480) -> bool:
    """Wait for the candidate to log in or navigate; never interact with credentials."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if _application_form_is_ready(page):
            return True
        page.wait_for_timeout(1_000)
    return False


def _prefill_page(page, job: dict, profile: dict, answers: dict) -> tuple[int, int]:
    verified = answers["verified_answers"]
    full_name = str(verified.get("full_name", "")).strip()
    name_parts = full_name.split()
    first_name = name_parts[0] if name_parts else ""
    last_name = name_parts[-1] if len(name_parts) > 1 else ""
    resume_path = profile.get("resumes", {}).get(job.get("resume_family"), "")
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
            # Some application platforms represent a requested base salary as a
            # numeric input.  It is still safe to fill only when its label is
            # recognised as salary or compensation below.
            if input_type not in {"text", "email", "tel", "url", "search", "number"} and element.evaluate("node => node.tagName.toLowerCase()") != "textarea":
                continue
            if "password" in descriptor:
                continue
            value = field_answer(descriptor, input_type, answers, job)
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
                    answers,
                    job,
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
        if not supports_supervised_browser_handoff(route):
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
            if route.support_level in {"login_required", "complex"}:
                _log(
                    database_path,
                    external_id,
                    "waiting_for_candidate",
                    "Sign in or complete the employer's account steps yourself. Applicant Zero will wait for an application form and will not enter credentials.",
                )
                if not _wait_for_candidate_handoff(page):
                    _log(database_path, external_id, "candidate_action_required", "No supported application form appeared during the supervised handoff. Continue manually on the employer site.")
                    while context.pages:
                        time.sleep(1)
                    _log(database_path, external_id, "closed", "The supervised browser was closed without Applicant Zero clicking submit.")
                    return
            # Multi-step forms are handled as a supervised loop.  On each new
            # page the assistant fills newly visible, verified fields.  It can
            # proceed through an ordinary "Next" step only when every required
            # field is already complete and no CAPTCHA is present.  It never
            # selects legal/identity answers and never clicks final submission.
            total_filled = 0
            last_signature = ""
            captcha_handoff_recorded = False
            while context.pages:
                page = context.pages[-1]
                try:
                    descriptors = page.locator("input, textarea, select").count()
                    signature = f"{page.url}|{descriptors}"
                    newly_filled, unresolved = _prefill_page(page, job, profile, answers)
                except Exception:
                    page.wait_for_timeout(750)
                    continue
                total_filled += newly_filled
                if signature != last_signature or newly_filled:
                    detail = (
                        f"Filled {total_filled} safe fields across the form. "
                        f"{unresolved} required fields remain highlighted for review. "
                        "Final submission was not clicked."
                    )
                    _log(database_path, external_id, "ready_for_review", detail)
                    last_signature = signature
                next_button = _next_step_button(page)
                if _captcha_present(page):
                    if not captcha_handoff_recorded:
                        with sqlite3.connect(database_path) as connection:
                            save_manual_action(
                                connection,
                                external_id,
                                "captcha",
                                "Complete employer CAPTCHA",
                                "The application page requires a human CAPTCHA check. Complete it in the open browser; Applicant Zero will continue with recognised fields after the page changes.",
                            )
                        _log(database_path, external_id, "candidate_action_required", "A CAPTCHA was detected and added to the manual action queue.")
                        captcha_handoff_recorded = True
                    page.wait_for_timeout(1_000)
                    continue
                if unresolved == 0 and next_button is not None:
                    next_button.click()
                    page.wait_for_timeout(1_000)
                    continue
                page.wait_for_timeout(1_000)
            _log(database_path, external_id, "closed", "The assisted browser was closed without Applicant Zero clicking submit.")
            if job["workflow_status"] in {"New", "Saved"}:
                with sqlite3.connect(database_path) as connection:
                    update_workflow(connection, external_id, "Preparing", job["notes"])
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
