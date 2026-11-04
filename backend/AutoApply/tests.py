import resumeRead
import Onboarding
import AnswerBankManager


def resumeTest():
    pdf_path = "C:\\Users\\Mjkon\\Downloads\\Konefal_ResumeCS_9_22.pdf"
    resumeText = resumeRead.readResume(pdf_path)
    assert resumeText is not None


def onboardingTest():
    pass


def answerBankLoadTest():
    pass