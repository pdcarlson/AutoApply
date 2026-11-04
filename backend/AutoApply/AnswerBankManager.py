import json


def SaveSingleResponse(user, question, answer):
    file = open("Bank.json", "w")
    data = json.load(file)
    data[user][question] = answer
    file.seek(0)


def SaveResponseDictionary(user, dict):
    file = open("Bank.json", "r")
    pass


def LoadData(user, question):
    file = open("Bank.json", "r")
    data = json.load(file)
    return data["userdata"][user][question]
