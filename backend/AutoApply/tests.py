import resumeRead
import Onboarding
import AnswerBankManager
import User


def resumeTest():
    pdf_path = "C:\\Users\\Mjkon\\Downloads\\Konefal_ResumeCS_9_22.pdf"
    resumeText = resumeRead.readResume(pdf_path)
    assert resumeText is not None
    print(resumeText["Projects"])
    return resumeText


def onboardingTest():
    Onboarding.askQuestion(User.testUserID, "0")
    Onboarding.askQuestion(User.testUserID, "1")


def answerBankSaveDictTest(resume):
    AnswerBankManager.SaveResponseDictionary(User.getTestUserID(), resume)


def answerBankLoadTest():
    data = AnswerBankManager.LoadData(User.getTestUserID(), "Projects")
    print(data)
    assert data is not None
