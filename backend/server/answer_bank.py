"""The Answer bank: structured answer records on top of Konefal's AnswerBankManager (spec 2.5).

`<data_dir>/answer_bank.json` is the single source of truth for answers. It keeps Konefal's
layout, `{"userdata": {"local": {<answer id>: <record>}}}`, and is read and written only through
AnswerBankManager. Keys are answer ids, not question text, so a global and a company-only answer
to the same question can coexist and PATCH can reword a question.

A record is the API `Answer` minus `savedRecently` (derived), plus:
    createdAt  ISO timestamp
    updatedAt  ISO timestamp of the last change (or null)
    origin     "onboarding" | "reply" | "manual" | "import"

Ids: `a-<8 hex>` for added and reply-saved answers, `onb-<CommonQuestionKey>` for setup answers.

Legacy values: a plain string under any key (e.g. from Konefal's CLI) reads as an "import"
record whose id and question are the key; it is written back as a record on its first edit.
Values that are neither strings nor dicts are ignored.

Every method holds the Store's RLock across load and save.
"""
from __future__ import annotations  # the `list` method would shadow list[...] annotations

import json
import logging
from datetime import timedelta
from pathlib import Path
from typing import Iterable

from agent.applicant.profile import SavedAnswer, normalize
from server import konefal
from server.store import DEMO_USER, Store, new_id, parse_iso

log = logging.getLogger(__name__)

ANSWER_CATEGORIES = ["Eligibility", "Education", "Logistics", "Pay", "Experience", "Self-ID"]
ORIGINS = ("onboarding", "reply", "manual", "import")
USER = DEMO_USER["id"]
USED_ON_CAP = 20
RECENT = timedelta(hours=24)
IMPORT_SOURCE = "Imported from your agent profile"

# Keyword checks in order (spec 2.8, guessCategory).
_CATEGORY_KEYWORDS = [
    (("sponsor", "authoriz", "eligib", "legally", "citizen", "clearance"), "Eligibility"),
    (("school", "degree", "gpa", "graduat", "university", "major"), "Education"),
    (("salary", "pay", "compensation"), "Pay"),
    (("gender", "race", "ethnic", "veteran", "disabilit", "pronoun"), "Self-ID"),
    (("start", "relocat", "location", "office", "on-site", "onsite", "remote", "hear about",
      "available"), "Logistics"),
]


def guess_category(label: str) -> str:
    """The Answer-bank category for a question, by keyword; "Experience" when nothing matches."""
    text = (label or "").lower()
    for keywords, category in _CATEGORY_KEYWORDS:
        if any(word in text for word in keywords):
            return category
    return "Experience"


def same_company(a: str | None, b: str | None) -> bool:
    return (a or "").strip().casefold() == (b or "").strip().casefold()


def _clean_company(company: str | None) -> str | None:
    company = (company or "").strip()
    return company or None


def _record_from(key: str, value) -> dict | None:
    """A full record from what's stored under `key`, or None for values we ignore."""
    if isinstance(value, str):
        return {
            "id": key, "category": guess_category(key), "question": key, "answer": value,
            "source": "Imported", "company": None, "timesUsed": 0, "lastUsedAt": None,
            "alsoMatches": [], "usedOn": [], "createdAt": None, "updatedAt": None,
            "origin": "import",
        }
    if not isinstance(value, dict):
        return None
    record = {
        "id": key,
        "category": value.get("category") if value.get("category") in ANSWER_CATEGORIES
        else guess_category(str(value.get("question") or key)),
        "question": str(value.get("question") or key),
        "answer": str(value.get("answer") if value.get("answer") is not None else ""),
        "source": str(value.get("source") or ""),
        "company": _clean_company(value.get("company")),
        "timesUsed": int(value.get("timesUsed") or 0),
        "lastUsedAt": value.get("lastUsedAt"),
        "alsoMatches": list(value.get("alsoMatches") or []),
        "usedOn": list(value.get("usedOn") or []),
        "createdAt": value.get("createdAt"),
        "updatedAt": value.get("updatedAt"),
        "origin": value.get("origin") if value.get("origin") in ORIGINS else "import",
    }
    return record


class AnswerBank:
    """Answer records for the local user. Set on `app.state.answer_bank` by create_app."""

    def __init__(self, store: Store, path: Path | str | None = None):
        self.store = store
        self.path = Path(path) if path is not None else konefal.bank_path(store.data_dir)

    # ----- raw access -----

    def _load(self) -> dict[str, dict]:
        """id -> record, for every usable entry of the local user."""
        with konefal.bank_file(self.path) as abm:
            try:
                raw = abm.LoadUser(USER)
            except (OSError, ValueError):
                log.warning("The Answer bank file is unreadable; treating it as empty",
                            exc_info=True)
                return {}
        if not isinstance(raw, dict):
            return {}
        out = {}
        for key, value in raw.items():
            record = _record_from(str(key), value)
            if record is not None:
                out[record["id"]] = record
        return out

    def _save(self, record: dict) -> None:
        with konefal.bank_file(self.path) as abm:
            abm.SaveSingleResponse(USER, record["id"], record)

    def _sorted(self, records: Iterable[dict]) -> list[dict]:
        return sorted(records, key=lambda r: r.get("createdAt") or "", reverse=True)

    # ----- serialization -----

    def saved_recently(self, record: dict) -> bool:
        if record.get("origin") != "reply":
            return False
        created = parse_iso(record.get("createdAt"))
        return created is not None and self.store.now() - created <= RECENT

    def to_api(self, record: dict) -> dict:
        """The API `Answer` (exactly the keys in frontend types.ts)."""
        return {
            "id": record["id"],
            "category": record["category"],
            "question": record["question"],
            "answer": record["answer"],
            "source": record["source"],
            "company": record["company"],
            "timesUsed": record["timesUsed"],
            "lastUsedAt": record["lastUsedAt"],
            "alsoMatches": record["alsoMatches"],
            "usedOn": record["usedOn"],
            "savedRecently": self.saved_recently(record),
        }

    # ----- reads -----

    def records(self) -> list[dict]:
        """Every record (with origin and createdAt), newest first."""
        with self.store.lock:
            return self._sorted(self._load().values())

    def record(self, answer_id: str) -> dict | None:
        """One record (with origin and createdAt), or None."""
        with self.store.lock:
            return self._load().get(answer_id)

    def list(self) -> list[dict]:
        """GET /answers: API Answers, newest first."""
        return [self.to_api(r) for r in self.records()]

    def get(self, answer_id: str) -> dict | None:
        record = self.record(answer_id)
        return self.to_api(record) if record is not None else None

    def is_empty(self) -> bool:
        with self.store.lock:
            return not self._load()

    def applicable(self, company: str | None) -> list[dict]:
        """Records that apply to `company`: company-specific ones first, then global ones."""
        records = self.records()
        own = [r for r in records
               if r["company"] and company and same_company(r["company"], company)]
        shared = [r for r in records if not r["company"]]
        return own + shared

    def projection(self, company: str | None) -> tuple[list[SavedAnswer], dict[str, str]]:
        """The bank as agent `Profile.answers` for one run, plus normalized wording -> record id.

        Each record gives its question and every `alsoMatches` wording. The first record for a
        wording wins (company-specific before global).
        """
        answers: list[SavedAnswer] = []
        ids: dict[str, str] = {}
        for record in self.applicable(company):
            wordings = [record["question"]] + [m.get("wording", "") for m in record["alsoMatches"]]
            for wording in wordings:
                key = normalize(wording)
                if not key or key in ids:
                    continue
                ids[key] = record["id"]
                answers.append(SavedAnswer(wording, record["answer"]))
        return answers, ids

    # ----- writes -----

    def _new_record(self, answer_id: str, *, question: str, answer: str, category: str | None,
                    company: str | None, origin: str, source: str) -> dict:
        return {
            "id": answer_id,
            "category": category if category in ANSWER_CATEGORIES else guess_category(question),
            "question": question,
            "answer": answer,
            "source": source,
            "company": _clean_company(company),
            "timesUsed": 0,
            "lastUsedAt": None,
            "alsoMatches": [],
            "usedOn": [],
            "createdAt": self.store.now_iso(),
            "updatedAt": None,
            "origin": origin,
        }

    def create(self, data: dict, origin: str, source: str) -> dict:
        """Adds a record from an AnswerInput-like dict; returns the API Answer."""
        with self.store.lock:
            existing = self._load()
            answer_id = new_id("a")
            while answer_id in existing:
                answer_id = new_id("a")
            record = self._new_record(
                answer_id, question=data["question"], answer=data["answer"],
                category=data.get("category"), company=data.get("company"),
                origin=origin, source=source)
            self._save(record)
            return self.to_api(record)

    def update(self, answer_id: str, patch: dict) -> dict | None:
        """Merges AnswerInput fields (category, question, answer, company); None if unknown."""
        with self.store.lock:
            record = self._load().get(answer_id)
            if record is None:
                return None
            for key in ("category", "question", "answer"):
                if key in patch and patch[key] is not None:
                    record[key] = patch[key]
            if "company" in patch:
                record["company"] = _clean_company(patch["company"])
            record["updatedAt"] = self.store.now_iso()
            self._save(record)
            return self.to_api(record)

    def delete(self, answer_id: str) -> bool:
        with self.store.lock:
            with konefal.bank_file(self.path) as abm:
                return abm.DeleteResponse(USER, answer_id)

    def put(self, answer_id: str, *, question: str, answer: str, category: str | None,
            origin: str, source: str, company: str | None = None) -> dict:
        """Creates or overwrites the record with a fixed id (setup's `onb-*`); keeps usage stats."""
        with self.store.lock:
            record = self._load().get(answer_id)
            if record is None:
                record = self._new_record(answer_id, question=question, answer=answer,
                                          category=category, company=company, origin=origin,
                                          source=source)
            else:
                changed = (record["question"], record["answer"]) != (question, answer)
                record.update(question=question, answer=answer, origin=origin, source=source,
                              company=_clean_company(company),
                              category=category if category in ANSWER_CATEGORIES
                              else record["category"])
                if changed:
                    record["updatedAt"] = self.store.now_iso()
            self._save(record)
            return self.to_api(record)

    def upsert_by_question(self, question: str, answer: str, company: str | None = None,
                           origin: str = "reply", source: str = "",
                           category: str | None = None) -> dict:
        """Sets the answer to `question` for `company` (None = every company).

        Matches an existing record on normalize(question) and the same company; otherwise adds
        one. Returns the API Answer.
        """
        with self.store.lock:
            wanted = normalize(question)
            for record in self._sorted(self._load().values()):
                if normalize(record["question"]) == wanted and \
                        same_company(record["company"], company):
                    record.update(answer=answer, origin=origin, source=source or record["source"],
                                  updatedAt=self.store.now_iso())
                    if category in ANSWER_CATEGORIES:
                        record["category"] = category
                    self._save(record)
                    return self.to_api(record)
            return self.create({"question": question, "answer": answer, "category": category,
                                "company": company}, origin=origin, source=source)

    def record_use(self, answer_id: str, company: str, wording: str | None = None) -> dict | None:
        """Counts one use on `company`'s form: timesUsed+1, lastUsedAt, usedOn (newest first,
        at most 20).

        A `wording` that differs from the record's question is added to `alsoMatches` once.
        """
        with self.store.lock:
            record = self._load().get(answer_id)
            if record is None:
                return None
            now = self.store.now_iso()
            record["timesUsed"] = int(record.get("timesUsed") or 0) + 1
            record["lastUsedAt"] = now
            record["usedOn"] = ([{"company": company, "at": now, "note": None}]
                                + list(record.get("usedOn") or []))[:USED_ON_CAP]
            if wording and normalize(wording) != normalize(record["question"]) and not any(
                    normalize(m.get("wording", "")) == normalize(wording)
                    for m in record["alsoMatches"]):
                record["alsoMatches"].append({"wording": wording, "seenOn": company})
            self._save(record)
            return self.to_api(record)

    # ----- one-time import (spec 2.5) -----

    def seed_from_profile(self, profile_path: Path | str) -> int:
        """Imports an agent profile JSON's `answers` into an empty bank. Never writes that file.

        Runs once per data dir (marker `state.bankSeeded`). Returns how many were imported.
        """
        with self.store.tx() as db:
            if db.state.get("bankSeeded"):
                return 0
            db.state["bankSeeded"] = True
            if not self.is_empty():
                return 0
            try:
                data = json.loads(Path(profile_path).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                log.warning("Couldn't read %s for the Answer bank import", profile_path)
                return 0
            items = data.get("answers") if isinstance(data, dict) else None
            count = 0
            for item in items or []:
                if not isinstance(item, dict):
                    continue
                question = str(item.get("question") or "").strip()
                answer = str(item.get("answer") or "").strip()
                if question and answer:
                    self.create({"question": question, "answer": answer}, origin="import",
                                source=IMPORT_SOURCE)
                    count += 1
            log.info("Imported %d answers from the agent profile into the Answer bank", count)
            return count
