"""Protected steps (CAPTCHAs, sign-ins, passwords, SSNs) the agent hands to the applicant."""
from agent.forms.protected.checks import (CaptchaCheck, LoginCheck, PageField, PasswordCheck,
                                          ProtectedCheck, SsnCheck)
from agent.forms.protected.detector import ProtectedFieldDetector
from agent.forms.protected.handoff import Handoff, HandoffKind, handoff_reason, merge

# Short names for the kinds, as other code imports them
CAPTCHA = HandoffKind.CAPTCHA
SSN = HandoffKind.SSN
PASSWORD = HandoffKind.PASSWORD
LOGIN = HandoffKind.LOGIN

__all__ = [
    "CAPTCHA", "LOGIN", "PASSWORD", "SSN", "CaptchaCheck", "Handoff", "HandoffKind",
    "LoginCheck", "PageField", "PasswordCheck", "ProtectedCheck", "ProtectedFieldDetector",
    "SsnCheck", "handoff_reason", "merge",
]
