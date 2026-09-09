from applicant_zero.browser_assist import _prefill_page
from applicant_zero.form_answers import field_answer, select_value


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
        return False

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


def test_form_answers_use_saved_work_rights_and_numeric_salary():
    answers = {
        "verified_answers": {
            "current_work_rights": "Full work rights",
            "requires_sponsorship": "No",
            "visa_type": "Student visa (subclass 500)",
            "citizenship_status": "No",
        },
        "answers_requiring_confirmation": {"salary_expectations": "AUD 85,000 base salary plus superannuation"},
    }
    assert field_answer("Do you need sponsorship?", "select", answers, {}) == "No"
    assert field_answer("Visa type", "text", answers, {}) == "Student visa (subclass 500)"
    assert field_answer("Base salary", "number", answers, {}) == "85000"
    assert select_value([("false", "No"), ("true", "Yes")], "No") == "false"
