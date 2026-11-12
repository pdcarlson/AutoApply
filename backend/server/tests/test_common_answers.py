"""PUT /common-answers mirrors the answers into `onb-*` Answer-bank records (spec 2.5)."""
from server.common_answers import answer_text, long_date


def _common(**overrides):
    body = {"workAuthorized": None, "needsSponsorship": None, "graduation": None,
            "earliestStart": None, "relocate": None, "locations": [], "expectedPay": "",
            "familyEmployers": [], "selfId": "ask", "skipped": []}
    body.update(overrides)
    return body


def _onb(client):
    return {a["id"]: a for a in client.get("/api/answers").json() if a["id"].startswith("onb-")}


def test_put_syncs_onboarding_records(client):
    body = _common(needsSponsorship="No", selfId="decline", graduation="May 2027",
                   skipped=["graduation"])
    response = client.put("/api/common-answers", json=body)
    assert response.status_code == 200 and response.json() == body
    assert client.get("/api/common-answers").json() == body

    onb = _onb(client)
    assert onb["onb-needsSponsorship"]["category"] == "Eligibility"
    assert onb["onb-needsSponsorship"]["answer"] == "No"
    assert onb["onb-needsSponsorship"]["question"] == \
        "Will you now or in the future require visa sponsorship?"
    assert onb["onb-needsSponsorship"]["source"] == "Onboarding · common questions"
    assert onb["onb-selfId"]["answer"] == "I don’t wish to answer"
    assert onb["onb-selfId"]["category"] == "Self-ID"
    assert "onb-graduation" not in onb
    assert "onb-workAuthorized" not in onb  # null
    assert onb["onb-familyEmployers"]["answer"] == "No"  # empty list means "No"

    body["skipped"] = []
    client.put("/api/common-answers", json=body)
    onb = _onb(client)
    assert onb["onb-graduation"]["answer"] == "May 2027"
    assert onb["onb-graduation"]["category"] == "Education"


def test_clearing_an_answer_deletes_its_record(client, app):
    client.put("/api/common-answers", json=_common(expectedPay="$30/hour", selfId="decline"))
    assert "onb-expectedPay" in _onb(client)
    app.state.answer_bank.record_use("onb-expectedPay", "Fake Company")
    client.put("/api/common-answers", json=_common(expectedPay="$32/hour", selfId="decline"))
    kept = _onb(client)["onb-expectedPay"]
    assert kept["answer"] == "$32/hour" and kept["timesUsed"] == 1  # usage survives a resave
    client.put("/api/common-answers", json=_common(expectedPay="", selfId="ask"))
    onb = _onb(client)
    assert "onb-expectedPay" not in onb and "onb-selfId" not in onb


def test_invalid_common_answers_are_rejected(client):
    response = client.put("/api/common-answers", json=_common(workAuthorized="Maybe"))
    assert response.status_code == 422 and response.json()["code"] == "invalid_request"


def test_answer_text_rules():
    common = _common(workAuthorized="Yes", relocate="Depends", earliestStart="2027-06-01",
                     locations=["Remote (US)", "New York, NY"], familyEmployers=["Acme", "Initech"],
                     selfId="decline")
    assert answer_text("workAuthorized", common) == "Yes"
    assert answer_text("relocate", common) == "Depends"
    assert answer_text("earliestStart", common) == "June 1, 2027"
    assert answer_text("locations", common) == "Remote (US); New York, NY"
    assert answer_text("familyEmployers", common) == "Possibly: Acme, Initech"
    assert answer_text("selfId", common) == "I don’t wish to answer"
    assert answer_text("expectedPay", common) is None
    assert long_date("not a date") == "not a date"
