import json

def askQuestions():
    with open("OnboardingQuestions.json", "r") as file:
        data = json.load(file)
        answers = {}
        for i in range(len(data)):
            print(data["questions"][i]["q"])
            answers.update({data["questions"][i]["q"]: input()})

