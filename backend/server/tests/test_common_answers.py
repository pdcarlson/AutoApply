"""PUT /common-answers mirrors the answers into `onb-*` Answer-bank records (spec 2.5)."""
import json

from server.common_answers import answer_text, long_date
from server.self_id import migrate_common_answers
from server.store import Store


def _common(**overrides):
    body = {"workAuthorized": None, "needsSponsorship": None, "graduation": None,
            "earliestStart": None, "relocate": None, "locations": [], "expectedPay": "",
            "familyEmployers": [], "gender": None, "hispanicLatino": None, "race": None,
            "veteran": None, "disability": None, "skipped": []}
    body.update(overrides)
    return body


def _onb(client):
    return {a["id"]: a for a in client.get("/api/answers").json() if a["id"].startswith("onb-")}


def test_put_syncs_onboarding_records(client):
    body = _common(needsSponsorship="No", gender="decline", graduation="May 2027",
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
    assert onb["onb-gender"]["answer"] == "I don’t wish to answer"
    assert onb["onb-gender"]["question"] == "Gender"
    assert onb["onb-gender"]["category"] == "Self-ID"
    assert "onb-veteran" not in onb  # not answered yet
    assert "onb-graduation" not in onb
    assert "onb-workAuthorized" not in onb  # null
    assert onb["onb-familyEmployers"]["answer"] == "No"  # empty list means "No"

    body["skipped"] = []
    client.put("/api/common-answers", json=body)
    onb = _onb(client)
    assert onb["onb-graduation"]["answer"] == "May 2027"
    assert onb["onb-graduation"]["category"] == "Education"


def test_clearing_an_answer_deletes_its_record(client, app):
    client.put("/api/common-answers", json=_common(expectedPay="$30/hour", gender="decline"))
    assert "onb-expectedPay" in _onb(client)
    app.state.answer_bank.record_use("onb-expectedPay", "Fake Company")
    client.put("/api/common-answers", json=_common(expectedPay="$32/hour", gender="decline"))
    kept = _onb(client)["onb-expectedPay"]
    assert kept["answer"] == "$32/hour" and kept["timesUsed"] == 1  # usage survives a resave
    client.put("/api/common-answers", json=_common(expectedPay="", gender=None))
    onb = _onb(client)
    assert "onb-expectedPay" not in onb and "onb-gender" not in onb


def test_invalid_common_answers_are_rejected(client):
    response = client.put("/api/common-answers", json=_common(workAuthorized="Maybe"))
    assert response.status_code == 422 and response.json()["code"] == "invalid_request"


def test_answer_text_rules():
    common = _common(workAuthorized="Yes", relocate="Depends", earliestStart="2027-06-01",
                     locations=["Remote (US)", "New York, NY"], familyEmployers=["Acme", "Initech"],
                     gender="Male", veteran="No", disability="decline")
    assert answer_text("workAuthorized", common) == "Yes"
    assert answer_text("relocate", common) == "Depends"
    assert answer_text("earliestStart", common) == "June 1, 2027"
    assert answer_text("locations", common) == "Remote (US); New York, NY"
    assert answer_text("familyEmployers", common) == "Possibly: Acme, Initech"
    assert answer_text("gender", common) == "Male"
    assert answer_text("veteran", common) == "I am not a protected veteran"
    assert answer_text("disability", common) == "I don’t wish to answer"
    assert answer_text("expectedPay", common) is None
    assert long_date("not a date") == "not a date"


def test_every_self_id_question_takes_an_answer_or_decline(client):
    body = _common(gender="Non-binary", hispanicLatino="No", race="Two or More Races",
                   veteran="Yes", disability="No")
    assert client.put("/api/common-answers", json=body).json() == body
    onb = _onb(client)
    assert onb["onb-gender"]["answer"] == "Non-binary"
    assert onb["onb-hispanicLatino"]["question"] == "Are you Hispanic/Latino?"
    assert onb["onb-hispanicLatino"]["answer"] == "No"
    assert onb["onb-race"]["answer"] == "Two or More Races"
    assert onb["onb-veteran"]["answer"] == "I identify as a protected veteran"
    assert onb["onb-disability"]["answer"] == "No, I don’t have a disability"
    assert {onb[f"onb-{k}"]["category"] for k in
            ("gender", "hispanicLatino", "race", "veteran", "disability")} == {"Self-ID"}

    declined = {k: "decline" for k in ("gender", "hispanicLatino", "race", "veteran",
                                       "disability")}
    client.put("/api/common-answers", json=_common(**declined))
    answers = {a["answer"] for k, a in _onb(client).items() if k != "onb-familyEmployers"}
    assert answers == {"I don’t wish to answer"}

    bad = client.put("/api/common-answers", json=_common(race="Martian"))
    assert bad.status_code == 422


def test_race_is_a_follow_up_to_hispanic_latino():
    assert answer_text("race", _common(hispanicLatino="No", race="White")) == "White"
    # Hispanic or Latino applicants aren't asked race; declining one declines both
    assert answer_text("race", _common(hispanicLatino="Yes", race="White")) is None
    declined = answer_text("race", _common(hispanicLatino="decline", race="White"))
    assert declined == "I don’t wish to answer"
    assert answer_text("race", _common(hispanicLatino=None, race="White")) is None


def test_the_old_single_self_id_question_is_migrated(tmp_path):
    legacy = _common()
    for key in ("gender", "hispanicLatino", "race", "veteran", "disability"):
        del legacy[key]
    legacy.update(selfId="decline", gender="Female", skipped=["selfId", "graduation"])
    (tmp_path / "common_answers.json").write_text(json.dumps(legacy), encoding="utf-8")

    common = Store(tmp_path).read("common_answers")
    assert "selfId" not in common
    assert common["gender"] == "Female"  # a newer answer wins
    assert common["race"] == common["veteran"] == "decline"
    assert common["skipped"] == ["graduation", "gender", "hispanicLatino", "race", "veteran",
                                 "disability"]
    assert migrate_common_answers({"selfId": "ask"}) == {}


def test_saving_deletes_the_old_self_id_record(app, client):
    app.state.answer_bank.put("onb-selfId", question="Voluntary self-identification",
                              answer="I don’t wish to answer", category="Self-ID",
                              origin="onboarding", source="Onboarding · common questions")
    client.put("/api/common-answers", json=_common())
    assert "onb-selfId" not in _onb(client)
