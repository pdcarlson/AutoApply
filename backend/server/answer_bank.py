"""The Answer bank: one user's saved answers, stored through the onboarding AnswerBankManager."""
from __future__ import annotations  # the `list` method would shadow list[...] annotations

import logging
from datetime import timedelta
from pathlib import Path
from typing import Iterable

from agent.applicant.profile import SavedAnswer, normalize
from server import onboarding_modules
from server.answer_record import (ANSWER_CATEGORIES, AnswerOrigin, AnswerRecord, clean_company,
                                  guess_category, same_company)
from server.store import Store, new_id, parse_iso

__all__ = ["ANSWER_CATEGORIES", "AnswerBank", "guess_category", "same_company"]

log = logging.getLogger(__name__)

USER = "local"  # the one key each user's own bank file keeps its answers under
USED_ON_CAP = 20
RECENT = timedelta(hours=24)


class AnswerBank:
    """One user's answer records in `<data_dir>/answer_bank.json`.

    The file keeps AnswerBankManager's layout, `{"userdata": {"local": {<answer id>: <record>}}}`.
    Keys are answer ids, not question text, so a global and a company-only answer to the same
    question can coexist. Every method holds the Store's lock across load and save.
    """

    def __init__(self, store: Store, path: Path | str | None = None):
        self.store = store
        self.path = Path(path) if path is not None else onboarding_modules.bank_path(store.data_dir)

    # ----- raw access -----

    def _load(self) -> dict[str, AnswerRecord]:
        """Return id -> record for every usable entry of the user."""
        with onboarding_modules.bank_file(self.path) as manager:
            try:
                raw = manager.LoadUser(USER)
            except (OSError, ValueError):
                log.warning("The Answer bank file is unreadable; treating it as empty",
                            exc_info=True)
                return {}
        if not isinstance(raw, dict):
            return {}
        records = (AnswerRecord.from_json(str(key), value) for key, value in raw.items())
        return {record.id: record for record in records if record is not None}

    def _save(self, record: AnswerRecord) -> None:
        """Write one record to the bank file."""
        with onboarding_modules.bank_file(self.path) as manager:
            manager.SaveSingleResponse(USER, record.id, record.to_json())

    @staticmethod
    def _newest_first(records: Iterable[AnswerRecord]) -> list[AnswerRecord]:
        """Return the records sorted newest first."""
        return sorted(records, key=lambda record: record.created_at or "", reverse=True)

    def _to_api(self, record: AnswerRecord) -> dict:
        """Return the API Answer for a record."""
        return record.to_api(self._saved_recently(record))

    def _saved_recently(self, record: AnswerRecord) -> bool:
        """Return True for a reply saved in the last day."""
        if record.origin is not AnswerOrigin.REPLY:
            return False
        created = parse_iso(record.created_at)
        return created is not None and self.store.now() - created <= RECENT

    # ----- reads -----

    def records(self) -> list[dict]:
        """Return every stored record (with origin and createdAt), newest first."""
        with self.store.lock:
            return [record.to_json() for record in self._newest_first(self._load().values())]

    def record(self, answer_id: str) -> dict | None:
        """Return one stored record (with origin and createdAt), or None."""
        with self.store.lock:
            record = self._load().get(answer_id)
            return record.to_json() if record is not None else None

    def list(self) -> list[dict]:
        """Return every API Answer, newest first."""
        with self.store.lock:
            return [self._to_api(record) for record in self._newest_first(self._load().values())]

    def get(self, answer_id: str) -> dict | None:
        """Return one API Answer, or None."""
        with self.store.lock:
            record = self._load().get(answer_id)
            return self._to_api(record) if record is not None else None

    def is_empty(self) -> bool:
        """Return True when the bank has no usable answers."""
        with self.store.lock:
            return not self._load()

    def projection(self, company: str | None) -> tuple[list[SavedAnswer], dict[str, str]]:
        """Return the bank as agent `Profile.answers` for one run, and wording -> record id.

        Each record gives its question and every `alsoMatches` wording. The first record for a
        wording wins: company-specific ones come before global ones.
        """
        answers: list[SavedAnswer] = []
        ids: dict[str, str] = {}
        for record in self._applicable_records(company):
            wordings = [record.question] + [match.get("wording", "")
                                            for match in record.also_matches]
            for wording in wordings:
                key = normalize(wording)
                if not key or key in ids:
                    continue
                ids[key] = record.id
                answers.append(SavedAnswer(wording, record.answer))
        return answers, ids

    def applicable(self, company: str | None) -> list[dict]:
        """Return the stored records that apply to `company`: its own first, then global ones."""
        return [record.to_json() for record in self._applicable_records(company)]

    def _applicable_records(self, company: str | None) -> list[AnswerRecord]:
        """Return the records that apply to `company`: its own first, then global ones."""
        with self.store.lock:
            records = self._newest_first(self._load().values())
        own = [record for record in records
               if record.company and company and same_company(record.company, company)]
        shared = [record for record in records if not record.company]
        return own + shared

    # ----- writes -----

    def _new_record(self, answer_id: str, data: dict, origin: str, source: str) -> AnswerRecord:
        """Return a new record from AnswerInput fields (question, answer, category, company)."""
        category = data.get("category")
        return AnswerRecord(
            id=answer_id,
            category=(category if category in ANSWER_CATEGORIES
                      else guess_category(data["question"])),
            question=data["question"],
            answer=data["answer"],
            source=source,
            company=clean_company(data.get("company")),
            created_at=self.store.now_iso(),
            origin=AnswerOrigin(origin),
        )

    def create(self, data: dict, origin: str, source: str) -> dict:
        """Add a record from an AnswerInput-like dict and return its API Answer."""
        with self.store.lock:
            existing = self._load()
            answer_id = new_id("a")
            while answer_id in existing:
                answer_id = new_id("a")
            record = self._new_record(answer_id, data, origin, source)
            self._save(record)
            return self._to_api(record)

    def update(self, answer_id: str, patch: dict) -> dict | None:
        """Merge AnswerInput fields into a record; return its API Answer, or None if unknown."""
        with self.store.lock:
            record = self._load().get(answer_id)
            if record is None:
                return None
            for key in ("category", "question", "answer"):
                if key in patch and patch[key] is not None:
                    setattr(record, key, patch[key])
            if "company" in patch:
                record.company = clean_company(patch["company"])
            record.updated_at = self.store.now_iso()
            self._save(record)
            return self._to_api(record)

    def delete(self, answer_id: str) -> bool:
        """Delete a record; return True if there was one."""
        with self.store.lock:
            with onboarding_modules.bank_file(self.path) as manager:
                return manager.DeleteResponse(USER, answer_id)

    def put(self, answer_id: str, *, question: str, answer: str,  # pylint: disable=too-many-arguments  # one keyword per record field
            category: str | None, origin: str, source: str, company: str | None = None) -> dict:
        """Create or overwrite the record with a fixed id (setup's `onb-*`), keeping its usage."""
        with self.store.lock:
            record = self._load().get(answer_id)
            if record is None:
                record = self._new_record(answer_id, {"question": question, "answer": answer,
                                                      "category": category,
                                                      "company": company}, origin, source)
            else:
                changed = (record.question, record.answer) != (question, answer)
                record.question, record.answer = question, answer
                record.origin, record.source = AnswerOrigin(origin), source
                record.company = clean_company(company)
                if category in ANSWER_CATEGORIES:
                    record.category = category
                if changed:
                    record.updated_at = self.store.now_iso()
            self._save(record)
            return self._to_api(record)

    def upsert_by_question(self, question: str, answer: str, company: str | None = None,
                           origin: str = "reply", source: str = "",
                           category: str | None = None) -> dict:
        """Set the answer to `question` for `company` (None means every company).

        Matches an existing record on normalize(question) and the same company; otherwise adds
        one. Returns the API Answer.
        """
        with self.store.lock:
            wanted = normalize(question)
            for record in self._newest_first(self._load().values()):
                if normalize(record.question) == wanted and same_company(record.company, company):
                    record.answer, record.origin = answer, AnswerOrigin(origin)
                    record.source = source or record.source
                    record.updated_at = self.store.now_iso()
                    if category in ANSWER_CATEGORIES:
                        record.category = category
                    self._save(record)
                    return self._to_api(record)
            return self.create({"question": question, "answer": answer, "category": category,
                                "company": company}, origin=origin, source=source)

    def record_use(self, answer_id: str, company: str, wording: str | None = None) -> dict | None:
        """Count one use on `company`'s form and return the API Answer, or None if unknown.

        Adds to timesUsed, lastUsedAt and usedOn (newest first, at most 20). A `wording` that
        differs from the record's question is added to `alsoMatches` once.
        """
        with self.store.lock:
            record = self._load().get(answer_id)
            if record is None:
                return None
            now = self.store.now_iso()
            record.times_used += 1
            record.last_used_at = now
            record.used_on = ([{"company": company, "at": now, "note": None}]
                              + record.used_on)[:USED_ON_CAP]
            if wording and not self._matches(record, wording):
                record.also_matches.append({"wording": wording, "seenOn": company})
            self._save(record)
            return self._to_api(record)

    @staticmethod
    def _matches(record: AnswerRecord, wording: str) -> bool:
        """Return True when the wording is the record's question or one it already matches."""
        wanted = normalize(wording)
        return wanted == normalize(record.question) or any(
            normalize(match.get("wording", "")) == wanted for match in record.also_matches)
