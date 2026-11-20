import resumeRead
import Onboarding
import tests


res = tests.resumeTest()
tests.answerBankSaveDictTest(res)
tests.answerBankLoadTest()
tests.onboardingTest()
# uncomment the below line to clear test data RECOMMEND TO DO THIS BEFORE PUSHING TO GIT
# tests.clearTestBank()


