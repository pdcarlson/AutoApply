import json
import os

import AnswerBankManager
import User

# Absolute, so it no longer depends on the current directory.
QUESTIONS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "OnboardingQuestions.json")


def loadQuestions():
    # questionID -> [prompt, bank key] (an optional third element is the Answer-bank category)
    with open(QUESTIONS_PATH, "r", encoding="utf-8") as file:
        return json.load(file)["questions"]


def saveAnswer(userID, questionID, answer):
    # Non-interactive version of askQuestion: saves the answer under the question's bank key.
    question = loadQuestions()[str(questionID)]
    AnswerBankManager.SaveSingleResponse(userID, question[1], answer)


def askQuestions(userID):
    answers = {}
    for questionID, question in loadQuestions().items():
        print(question[0])
        answers.update({question[1]: input()})
    AnswerBankManager.SaveResponseDictionary(userID, answers)


def askQuestion(userID, questionID):
    question = loadQuestions()[str(questionID)]
    answer = input(question[0])
    AnswerBankManager.SaveSingleResponse(userID, question[1], answer)
