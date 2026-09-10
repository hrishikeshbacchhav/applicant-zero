from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


SUPERVISED_BROWSER_LEVELS = frozenset({"assisted", "pilot", "login_required", "complex"})


@dataclass(frozen=True)
class ApplicationRoute:
    platform: str
    support_level: str
    apply_url: str
    account_required: bool = False
    captcha_detected: bool = False
    field_count: int = 0
    required_field_count: int = 0
    detail: str = ""


class _FormInspector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.field_count = 0
        self.required_field_count = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in {"input", "select", "textarea"}:
            return
        attributes = dict(attrs)
        input_type = (attributes.get("type") or "text").lower()
        if input_type in {"hidden", "submit", "button", "reset", "image"}:
            return
        self.field_count += 1
        if "required" in attributes or attributes.get("aria-required") == "true":
            self.required_field_count += 1


def supports_supervised_browser_handoff(route: "ApplicationRoute") -> bool:
    """A candidate may open these routes with the assistant; it never handles login or submit."""
    return route.support_level in SUPERVISED_BROWSER_LEVELS


def classify_application_url(url: str) -> ApplicationRoute:
    parsed = urlsplit(url)
    host = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    if host == "jobs.lever.co" or host.endswith(".lever.co"):
        apply_path = path if path.endswith("/apply") else path + "/apply"
        apply_url = urlunsplit((parsed.scheme or "https", parsed.netloc, apply_path, "", ""))
        return ApplicationRoute("Lever", "assisted", apply_url, detail="Direct hosted application form; no employer account is normally required.")
    if "greenhouse.io" in host:
        return ApplicationRoute("Greenhouse", "pilot", url, detail="Direct hosted application form available for supervised browser testing; no employer account is normally required.")
    if "myworkdayjobs.com" in host or "workday.com" in host:
        return ApplicationRoute("Workday", "complex", url, account_required=True, detail="Multi-step application that may require an employer account.")
    if "seek.com" in host:
        return ApplicationRoute("SEEK", "login_required", url, account_required=True, detail="Application normally uses the candidate's SEEK account.")
    if "linkedin.com" in host:
        return ApplicationRoute("LinkedIn", "login_required", url, account_required=True, detail="Application requires the candidate's LinkedIn session.")
    if "ashbyhq.com" in host:
        return ApplicationRoute("Ashby", "pilot", url, detail="Hosted application form suitable for a supervised pilot.")
    if "workable.com" in host:
        return ApplicationRoute("Workable", "pilot", url, detail="Hosted application form suitable for a supervised pilot; review any employer-specific questions.")
    if "smartrecruiters.com" in host:
        return ApplicationRoute("SmartRecruiters", "pilot", url, detail="Hosted application form suitable for a supervised pilot; review any employer-specific questions.")
    return ApplicationRoute("Other", "manual_review", url, detail="Application route must be reviewed before browser assistance.")


def inspect_application_route(url: str) -> ApplicationRoute:
    base = classify_application_url(url)
    request = Request(base.apply_url, headers={"User-Agent": "Applicant-Zero/0.1 application compatibility check"})
    with urlopen(request, timeout=20) as response:
        text = response.read().decode("utf-8", errors="replace")
    parser = _FormInspector()
    parser.feed(text)
    lowered = text.lower()
    captcha = any(marker in lowered for marker in ("recaptcha", "hcaptcha", "captcha"))
    account_required = base.account_required
    if base.platform not in {"Lever", "Greenhouse"}:
        account_required = account_required or any(marker in lowered for marker in ("create an account", "sign in to apply", "log in to apply"))
    detail = base.detail
    if parser.field_count:
        detail += f" Detected {parser.field_count} form fields, including {parser.required_field_count} marked required in the initial HTML."
    else:
        detail += " No application fields were visible in the initial HTML; the page may render them with JavaScript."
    if captcha:
        detail += " A CAPTCHA marker was detected and will require the candidate."
    return ApplicationRoute(
        base.platform,
        base.support_level,
        base.apply_url,
        account_required,
        captcha,
        parser.field_count,
        parser.required_field_count,
        detail,
    )
