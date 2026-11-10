import json
import AnswerBankManager
import User


# broken, will fix
def askQuestions(userID):
    with open("OnboardingQuestions.json", "r") as file:
        data = json.load(file)
        answers = {}
        for i in range(len(data)):
            print(data["questions"][i]["q"])
            answers.update({data["questions"][i]["q"]: input()})
        AnswerBankManager.SaveResponseDictionary(userID, answers)


def askQuestion(userID, questionID):
    with open("OnboardingQuestions.json", "r") as file:
        data = json.load(file)
        answer = input(data["questions"][questionID][0])
        AnswerBankManager.SaveSingleResponse(userID, data["questions"][questionID][1], answer)
