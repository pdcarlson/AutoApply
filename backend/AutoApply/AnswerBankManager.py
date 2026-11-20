import json
import os

bankPath = "Bank.json"
# make into a class
# update names of functions to match convention
# set up a consistent naming standard
# don't load bank every time.  cache class instead


def LoadBank():
    if not os.path.exists(bankPath):
        return {"userdata": {}}
    with open(bankPath, "r") as f:
        data = json.load(f)
        if not isinstance(data, dict):
            return {"userdata": {}}
        if not isinstance(data.get("userdata"), dict):
            data["userdata"] = {}
        return data


def SaveBank(data):
    with open(bankPath, "w") as f:
        json.dump(data, f, indent=4)


def UserExists(user):
    data = LoadBank()
    return str(user) in data["userdata"].keys()


def SaveSingleResponse(user, question, answer):
    data = LoadBank()
    data["userdata"][str(user)][question] = answer
    SaveBank(data)


def SaveResponseDictionary(user, resp):
    data = LoadBank()
    data.setdefault("userdata", {}).setdefault(str(user), {}).update(resp)
    SaveBank(data)


def LoadData(user, question):
    data = LoadBank()
    return data.get("userdata", {}).get(str(user), {}).get(question)


def LoadFullUserData(user):
    data = LoadBank()
    return data.get("userdata", {}).get(str(user))


def LoadUser(user):
    data = LoadBank()
    return data["userdata"].get(str(user), {})


def ClearUser(user):
    data = LoadBank()
    data.setdefault("userdata", {}).setdefault(str(user), {}).clear()
    SaveBank(data)


def WipeDict():
    data = LoadBank()
    data.setdefault("userdata", {}).clear()
    SaveBank(data)
