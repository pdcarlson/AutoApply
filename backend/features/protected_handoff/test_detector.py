"""Protected-field detection (US8). No browser needed: pages are faked."""
from features.protected_handoff.detector import (
    CAPTCHA, COLLECT_FIELDS_JS, LOGIN, PASSWORD, SSN,
    FormField, ProtectedFieldDetector, needs_you_reason)

detector = ProtectedFieldDetector()


def kind_of(field):
    handoff = detector.check_field(field)
    return handoff.kind if handoff else None


def test_ssn_fields_in_every_spelling():
    assert kind_of(FormField(label="Social Security Number")) == SSN
    assert kind_of(FormField(label="Last 4 of SSN")) == SSN
    assert kind_of(FormField(name="social_security_number")) == SSN
    assert kind_of(FormField(element_id="applicant-ssn")) == SSN


def test_password_boxes():
    assert kind_of(FormField(label="Create a password", input_type="password")) == PASSWORD
    assert kind_of(FormField(name="pw", autocomplete="new-password")) == PASSWORD


def test_login_and_codes():
    assert kind_of(FormField(label="Username*")) == LOGIN
    assert kind_of(FormField(label="Enter the verification code we emailed you")) == LOGIN
    assert kind_of(FormField(name="otp")) == LOGIN
    assert kind_of(FormField(name="user", autocomplete="username")) == LOGIN


def test_captcha_response_fields():
    assert kind_of(FormField(name="g-recaptcha-response", input_type="textarea")) == CAPTCHA
    assert kind_of(FormField(name="cf-turnstile-response", input_type="hidden")) == CAPTCHA


def test_normal_questions_are_left_for_the_agent():
    normal = [
        FormField(label="First name"),
        FormField(label="Email", input_type="email", autocomplete="email"),
        FormField(label="Phone", input_type="tel"),
        FormField(label="GitHub username"),
        FormField(label="LinkedIn profile"),
        FormField(label="Why do you want to work here?", input_type="textarea"),
        FormField(label="Are you legally authorized to work in the US?", input_type="select"),
    ]
    assert detector.scan_fields(normal) == []


class FakeFrame:
    def __init__(self, url):
        self.url = url


class FakePage:
    def __init__(self, fields, frame_urls=()):
        self._fields = fields
        self.frames = [FakeFrame(u) for u in frame_urls]

    def evaluate(self, script):
        assert script == COLLECT_FIELDS_JS
        return self._fields


def raw(label, **extra):
    base = {"label": label, "name": "", "element_id": "", "input_type": "text",
            "autocomplete": "", "placeholder": ""}
    base.update(extra)
    return base


def test_scan_page_finds_captcha_iframe():
    page = FakePage([raw("First name")],
                    frame_urls=["https://boards.greenhouse.io/x",
                                "https://www.google.com/recaptcha/api2/anchor?k=abc"])
    assert [h.kind for h in detector.scan_page(page)] == [CAPTCHA]


def test_scan_page_clean_form():
    page = FakePage([raw("First name"), raw("Resume", input_type="file")],
                    frame_urls=["https://jobs.lever.co/x"])
    assert not detector.scan_page(page)


def test_reason_lists_each_kind_once():
    page = FakePage([raw("SSN"), raw("Confirm SSN"), raw("Password", input_type="password")])
    reason = needs_you_reason(detector.scan_page(page))
    assert reason.count("Social Security") == 1
    assert "password" in reason


def test_field_values_are_never_read():
    assert ".value" not in COLLECT_FIELDS_JS
