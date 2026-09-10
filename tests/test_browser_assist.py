from applicant_zero.browser_assist import _next_step_button, _prefill_page, _submit_button_present
from applicant_zero.form_answers import field_answer, option_matches, select_value


class FakeElement:
    def __init__(self, attrs, *, visible=True):
        self.attrs = attrs
        self.visible = visible
        self.value = ""
        self.file = ""
        self.highlighted = False

    def get_attribute(self, name):
        return self.attrs.get(name)

    def is_visible(self):
        return self.visible

    def is_enabled(self):
        return True

    def is_checked(self):
        return bool(self.attrs.get("checked", False))

    def check(self):
        self.attrs["checked"] = True

    def input_value(self):
        return self.value

    def fill(self, value):
        self.value = value

    def set_input_files(self, value):
        self.file = value
        self.value = value

    def evaluate(self, script):
        if "tagName" in script:
            return self.attrs.get("tag", "input")
        if "CSS.escape" in script:
            return self.attrs.get("label", "")
        self.highlighted = True


class FakeLocator:
    def __init__(self, elements):
        self.elements = elements

    def count(self):
        return len(self.elements)

    def nth(self, index):
        return self.elements[index]


class FakePage:
    def __init__(self, elements):
        self.elements = elements

    def locator(self, selector):
        if "required" in selector:
            return FakeLocator([
                element for element in self.elements
                if "required" in element.attrs or element.attrs.get("aria-required") == "true"
            ])
        return FakeLocator(self.elements)


class FakeButton:
    def __init__(self, label, *, enabled=True):
        self.label = label
        self.enabled = enabled

    def is_visible(self):
        return True

    def is_enabled(self):
        return self.enabled

    def inner_text(self):
        return self.label

    def get_attribute(self, name):
        return self.label if name in {"value", "aria-label"} else None


class FakeButtonPage:
    def __init__(self, buttons):
        self.buttons = buttons

    def locator(self, _selector):
        return FakeLocator(self.buttons)


def test_prefill_uses_confirmed_answers_and_leaves_work_rights_unanswered(tmp_path):
    resume = tmp_path / "resume.pdf"
    resume.write_text("resume", encoding="utf-8")
    first_name = FakeElement({"name": "first_name", "required": ""})
    email = FakeElement({"name": "email", "type": "email", "required": ""})
    salary = FakeElement({"name": "form_field_7", "type": "number", "label": "Base salary", "required": ""})
    work_rights = FakeElement({"name": "work_rights_visa", "required": ""})
    resume_field = FakeElement({"name": "resume", "type": "file", "required": ""}, visible=False)
    page = FakePage([first_name, email, salary, work_rights, resume_field])
    profile = {"resumes": {"data_bi": str(resume)}}
    job = {"resume_family": "data_bi"}
    answers = {
        "verified_answers": {
            "full_name": "Rishi Example",
            "email": "rishi@example.com",
            "phone": "",
            "current_location": "Sydney",
            "available_from": "2026-11-15",
        },
        "answers_requiring_confirmation": {
            "salary_expectations": "AUD 80,000 plus super",
            "notice_period": "",
            "linkedin_url": "",
            "portfolio_url": "",
            "referral_source": "",
        },
    }
    filled, unresolved = _prefill_page(page, job, profile, answers)
    assert filled == 4
    assert first_name.value == "Rishi"
    assert email.value == "rishi@example.com"
    assert salary.value == "80000"
    assert resume_field.file == str(resume)
    assert work_rights.value == ""
    assert work_rights.highlighted is True
    assert unresolved == 1


def test_form_answers_keep_protected_eligibility_fields_for_candidate_review():
    answers = {
        "verified_answers": {
            "current_work_rights": "Full work rights",
            "requires_sponsorship": "No",
            "visa_type": "Student visa (subclass 500)",
            "citizenship_status": "No",
        },
        "answers_requiring_confirmation": {"salary_expectations": "AUD 85,000 base salary plus superannuation"},
    }
    assert field_answer("Do you need sponsorship?", "select", answers, {}) == ""
    assert field_answer("Visa type", "text", answers, {}) == ""
    assert field_answer("Base salary", "number", answers, {}) == "85000"
    assert select_value([("false", "No"), ("true", "Yes")], "No") == "false"
    assert option_matches("No", "false", "No") is True
    assert option_matches("No", "true", "Yes") is False


def test_form_answers_use_saved_structured_address_parts_when_available():
    answers = {
        "verified_answers": {"address": "Unit 1, Example Road", "state": "NSW", "postcode": "2145", "country": "Australia"},
        "answers_requiring_confirmation": {},
    }
    assert field_answer("Postcode", "text", answers, {}) == "2145"
    assert field_answer("State / province", "select", answers, {}) == "NSW"
    assert field_answer("Country", "select", answers, {}) == "Australia"


def test_prefill_keeps_sponsorship_radio_for_candidate_review(tmp_path):
    available = FakeElement({"name": "start_date", "type": "date", "required": ""})
    sponsorship_no = FakeElement({"name": "sponsorship", "type": "radio", "value": "no", "label": "Do you require sponsorship? No", "required": ""})
    sponsorship_yes = FakeElement({"name": "sponsorship", "type": "radio", "value": "yes", "label": "Do you require sponsorship? Yes", "required": ""})
    page = FakePage([available, sponsorship_no, sponsorship_yes])
    answers = {
        "verified_answers": {"available_from": "2026-11-15", "requires_sponsorship": "No"},
        "answers_requiring_confirmation": {},
    }
    filled, unresolved = _prefill_page(page, {"resume_family": "data_bi"}, {"resumes": {}}, answers)
    assert filled == 1
    assert available.value == "2026-11-15"
    assert sponsorship_no.is_checked() is False
    assert sponsorship_yes.is_checked() is False
    assert unresolved >= 1


def test_multi_step_controls_allow_next_but_never_treat_submit_as_progression():
    page = FakeButtonPage([FakeButton("Continue"), FakeButton("Submit application")])
    assert _next_step_button(page).inner_text() == "Continue"
    assert _submit_button_present(page) is True


def test_final_submission_only_page_has_no_safe_next_step():
    page = FakeButtonPage([FakeButton("Submit application")])
    assert _next_step_button(page) is None
    assert _submit_button_present(page) is True
