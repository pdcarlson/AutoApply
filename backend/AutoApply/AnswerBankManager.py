import json
import os
import time

# Absolute, so it no longer depends on the current directory. The server calls setBankPath()
# to point it at its own data directory.
bankPath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Bank.json")


def setBankPath(path):
    global bankPath
    bankPath = str(path)


def getBankPath():
    return bankPath


def LoadBank():
    if not os.path.exists(bankPath):
        return {"userdata": {}}
    with open(bankPath, "r", encoding="utf-8") as f:
        data = json.load(f)
        if not isinstance(data, dict):
            return {"userdata": {}}
        if not isinstance(data.get("userdata"), dict):
            data["userdata"] = {}
        return data


def SaveBank(data):
    # Write a temp file next to the bank, then swap it in, so a crash never leaves half a file.
    folder = os.path.dirname(os.path.abspath(bankPath))
    os.makedirs(folder, exist_ok=True)
    tmpPath = bankPath + ".tmp"
    try:
        with open(tmpPath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        for attempt in range(5):
            try:
                os.replace(tmpPath, bankPath)
                break
            except PermissionError:  # Windows: the file is briefly open elsewhere
                if attempt == 4:
                    raise
                time.sleep(0.05)
    finally:
        if os.path.exists(tmpPath):
            os.remove(tmpPath)


def UserExists(user):
    data = LoadBank()
    return data["userdata"].keys().__contains__(str(user))


def SaveSingleResponse(user, question, answer):
    data = LoadBank()
    data["userdata"].setdefault(str(user), {})[question] = answer
    SaveBank(data)


def SaveResponseDictionary(user, resp):
    data = LoadBank()
    # update changed fields in the dictionary, while leaving fields that haven't been updated alone.
    data.setdefault("userdata", {}).setdefault(str(user), {}).update(resp)
    SaveBank(data)


def DeleteResponse(user, question):
    # Returns True when there was something to delete.
    data = LoadBank()
    userData = data["userdata"].get(str(user))
    if not isinstance(userData, dict) or question not in userData:
        return False
    del userData[question]
    SaveBank(data)
    return True


def LoadData(user, question):
    data = LoadBank()
    return data.get("userdata", {}).get(str(user), {}).get(question)


def LoadUser(user):
    data = LoadBank()
    return data["userdata"].get(str(user), {})
