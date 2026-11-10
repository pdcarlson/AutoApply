import resumeRead
import Onboarding
import tests


res = tests.resumeTest()
tests.answerBankSaveDictTest(res)
tests.answerBankLoadTest()
tests.onboardingTest()

