import json
import os

bankPath = "Bank.json"


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
    return data["userdata"].keys().__contains__(str(user))


def SaveSingleResponse(user, question, answer):
    data = LoadBank()
    data["userdata"][str(user)][question] = answer
    SaveBank(data)


def SaveResponseDictionary(user, resp):
    data = LoadBank()
    if not UserExists(user):
        data.setdefault("userdata", {}).setdefault(str(user), {}).update(resp)
    else:
        # update changed fields in the dictionary, while leaving fields that haven't been updated alone.
        # union all fields that are not in both the dictionary and json
        pass
    SaveBank(data)



def LoadData(user, question):
    data = LoadBank()
    return data.get("userdata", {}).get(str(user), {}).get(question)


def LoadUser(user):
    data = LoadBank()
    return data["userdata"].get(str(user), {})
