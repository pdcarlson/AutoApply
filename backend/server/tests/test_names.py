"""The split name (firstName/middleName/lastName) and the migration of a legacy `name`."""
import json

import pytest
from fastapi.testclient import TestClient

from server.names import full_name, migrate_profile, split_name
from server.store import Store


@pytest.mark.parametrize("full, parts", [
    ("", ("", "", "")),
    ("Cher", ("Cher", "", "")),
    ("Jordan Rivera", ("Jordan", "", "Rivera")),
    ("  Mary   Ann  Smith ", ("Mary", "Ann", "Smith")),
    ("Ada Byron King Lovelace", ("Ada", "Byron King", "Lovelace")),
    ("Martin Luther King Jr.", ("Martin", "Luther", "King Jr.")),
    ("Ludwig van Beethoven", ("Ludwig", "", "van Beethoven")),
])
def test_split_name(full, parts):
    assert split_name(full) == parts


def test_full_name_skips_empty_parts():
    assert full_name({"firstName": "Mary", "middleName": "Ann", "lastName": "Smith"}) == \
        "Mary Ann Smith"
    assert full_name({"firstName": "Mary", "middleName": " ", "lastName": "Smith"}) == "Mary Smith"
    assert full_name({}) == ""


def test_migrate_profile_splits_a_legacy_name():
    assert migrate_profile({"name": "Mary Ann Smith", "email": "m@example.com"}) == {
        "firstName": "Mary", "middleName": "Ann", "lastName": "Smith", "email": "m@example.com"}
    # Already split: the stored fields win and the stale `name` is dropped.
    assert migrate_profile({"name": "Old Name", "firstName": "New", "lastName": "Person"}) == {
        "firstName": "New", "lastName": "Person"}
    current = {"firstName": "A", "middleName": "", "lastName": "B"}
    assert migrate_profile(current) is current


def test_store_migrates_a_legacy_profile_on_load(tmp_path):
    (tmp_path / "profile.json").write_text(
        json.dumps({"name": "Jordan Rivera", "email": "jordan@example.com", "city": "Troy"}),
        encoding="utf-8")
    store = Store(tmp_path)
    profile = store.read("profile")
    assert (profile["firstName"], profile["middleName"], profile["lastName"]) == (
        "Jordan", "", "Rivera")
    assert "name" not in profile
    assert profile["city"] == "Troy" and profile["links"]  # missing keys still get defaults
    # The file on disk is left alone until the profile next changes.
    assert "name" in json.loads((tmp_path / "profile.json").read_text(encoding="utf-8"))
    with store.tx() as db:
        db.profile["phone"] = "555"
    saved = json.loads((tmp_path / "profile.json").read_text(encoding="utf-8"))
    assert "name" not in saved and saved["firstName"] == "Jordan"


def test_legacy_profile_works_through_the_api(make_app, data_dir):
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "profile.json").write_text(json.dumps({"name": "Mary Ann Smith"}),
                                           encoding="utf-8")
    with TestClient(make_app()) as client:
        client.post("/api/auth/google", json={"returnTo": "/"})
        profile = client.get("/api/profile").json()
        assert (profile["firstName"], profile["middleName"], profile["lastName"]) == (
            "Mary", "Ann", "Smith")
        assert "name" not in profile
        assert client.get("/api/session").json()["user"]["name"] == "Mary Ann Smith"
        exported = client.get("/api/account/export").json()["profile"]
        assert exported["firstName"] == "Mary" and "name" not in exported
