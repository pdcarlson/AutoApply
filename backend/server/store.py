"""JSON-document storage for the single local user.

Every document in DOC_DEFAULTS lives in memory and in `<data_dir>/<name>.json`. One RLock guards
all of them; use `with store.tx() as db:` for any read-modify-write. On a clean exit the docs the
block changed are written atomically (tmp file + os.replace). If the block raises, the in-memory
docs it touched are rolled back and nothing is written.

`answer_bank.json` is not a Store doc: AnswerBankManager owns that file (WP2), but callers still
hold `store.lock` around it.

One process per data dir. There is no cross-process file lock.
"""
import copy
import json
import logging
import os
import secrets
import shutil
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

from fastapi import Request

from server.names import migrate_profile, split_name
from server.self_id import migrate_common_answers

log = logging.getLogger(__name__)

SCHEMA = 1
DEMO_USER = {"id": "local", "name": "Demo User", "email": "demo@example.com"}


def default_state() -> dict:
    return {"schema": SCHEMA, "signedIn": False, "profileConfirmed": False, "paused": False,
            "queue": []}


def default_profile() -> dict:
    """`emptyProfile()` from frontend/src/mocks/db.ts, with the demo user's name and email."""
    first, middle, last = split_name(DEMO_USER["name"])
    return {
        "firstName": first, "middleName": middle, "lastName": last,
        "email": DEMO_USER["email"],
        "phone": "", "street": "", "street2": "", "city": "", "state": "", "zip": "",
        "country": "United States",
        "links": [
            {"id": "web", "label": "Website / portfolio", "url": "", "fixed": True},
            {"id": "linkedin", "label": "LinkedIn", "url": "", "fixed": True},
            {"id": "github", "label": "GitHub", "url": "", "fixed": True},
        ],
        "education": [], "experience": [], "projects": [], "skills": [], "custom": [],
        "resume": None,
        "unplaced": [],
    }


def default_common_answers() -> dict:
    return {
        "workAuthorized": None, "needsSponsorship": None, "graduation": None, "earliestStart": None,
        "relocate": None, "locations": ["Remote (US)"], "expectedPay": "", "familyEmployers": [],
        "gender": None, "hispanicLatino": None, "race": None, "veteran": None, "disability": None,
        "skipped": [],
    }


def default_preferences() -> dict:
    return {"roleTypes": [], "fullTime": True, "internship": False}


def default_settings() -> dict:
    return {"confidenceThreshold": 90, "dailyLimit": 25}


# Doc name -> factory for its default value. The file is `<name>.json`. Add docs here.
DOC_DEFAULTS: dict[str, Callable[[], Any]] = {
    "state": default_state,
    "profile": default_profile,
    "resume_parse": lambda: None,
    "common_answers": default_common_answers,
    "preferences": default_preferences,
    "settings": default_settings,
    "jobs": list,
    "applications": list,
}

# Doc name -> function that upgrades a doc saved by an older version, applied on load before
# missing keys get their defaults. The upgraded doc is written back on its next change.
DOC_MIGRATIONS: dict[str, Callable[[Any], Any]] = {
    "profile": migrate_profile,
    "common_answers": migrate_common_answers,
}

GITIGNORE = ".gitignore"


def new_id(prefix: str) -> str:
    """`<prefix>-<8 hex>`, e.g. new_id("a") -> "a-1f2e3d4c"."""
    return f"{prefix}-{secrets.token_hex(4)}"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(moment: datetime) -> str:
    """ISO 8601 in UTC with a Z suffix and whole seconds: 2026-10-20T13:41:00Z."""
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def atomic_write_text(path: Path, text: str) -> None:
    """Writes `path` through `path.tmp` and os.replace, so readers never see half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        for attempt in range(5):
            try:
                os.replace(tmp, path)
                break
            except PermissionError:  # Windows: the target is briefly open elsewhere (AV, indexer)
                if attempt == 4:
                    raise
                time.sleep(0.05)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


class Db:
    """The view a `store.tx()` block works on: `db.<doc name>` is the live in-memory doc.

    Reading a doc snapshots it; on exit only docs whose JSON changed are saved. Assigning
    `db.jobs = [...]` replaces a doc.
    """

    def __init__(self, store: "Store"):
        object.__setattr__(self, "_store", store)
        object.__setattr__(self, "_snapshots", {})

    def _touch(self, name: str) -> None:
        if name not in DOC_DEFAULTS:
            raise AttributeError(f"Unknown store doc {name!r}")
        if name not in self._snapshots:
            self._snapshots[name] = _dump(self._store._docs[name])  # pylint: disable=protected-access

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        self._touch(name)
        return self._store._docs[name]  # pylint: disable=protected-access

    def __setattr__(self, name: str, value: Any) -> None:
        self._touch(name)
        self._store._docs[name] = value  # pylint: disable=protected-access

    def _changed(self) -> list[tuple[str, str]]:
        """(name, new JSON) for each touched doc that changed. Raises if a doc isn't JSON."""
        docs = self._store._docs  # pylint: disable=protected-access
        out = []
        for name, before in self._snapshots.items():
            after = _dump(docs[name])
            if after != before:
                out.append((name, after))
        return out

    def _rollback(self) -> None:
        docs = self._store._docs  # pylint: disable=protected-access
        for name, before in self._snapshots.items():
            docs[name] = json.loads(before)


class Store:
    """All JSON docs of one data dir, guarded by one RLock."""

    def __init__(self, data_dir: Path | str, clock: Callable[[], datetime] = utc_now):
        self.data_dir = Path(data_dir)
        self.lock = threading.RLock()
        self.clock = clock
        self._tx_db: Db | None = None
        self._tx_depth = 0
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_gitignore()
        self._docs: dict[str, Any] = {name: self._load(name) for name in DOC_DEFAULTS}

    # ----- clock -----

    def now(self) -> datetime:
        """Current time (UTC, timezone-aware). Tests can pass a fake `clock`."""
        return self.clock()

    def now_iso(self) -> str:
        return iso(self.now())

    # ----- paths -----

    def path(self, *parts: str) -> Path:
        """A path inside the data dir (not created)."""
        return self.data_dir.joinpath(*parts)

    def dir(self, *parts: str) -> Path:
        """A sub-directory of the data dir, created if needed (e.g. store.dir("screenshots"))."""
        target = self.path(*parts)
        target.mkdir(parents=True, exist_ok=True)
        return target

    def doc_path(self, name: str) -> Path:
        return self.path(f"{name}.json")

    # ----- transactions -----

    @contextmanager
    def tx(self) -> Iterator[Db]:
        """`with store.tx() as db:` holds the lock; saves changed docs on a clean exit.

        Nested tx() calls in the same thread join the outer one; it saves at the outermost exit.
        """
        with self.lock:
            if self._tx_db is not None:
                self._tx_depth += 1
                try:
                    yield self._tx_db
                finally:
                    self._tx_depth -= 1
                return
            db = Db(self)
            self._tx_db, self._tx_depth = db, 1
            try:
                yield db
                changed = db._changed()  # pylint: disable=protected-access
                for name, text in changed:
                    atomic_write_text(self.doc_path(name), text)
            except BaseException:
                db._rollback()  # pylint: disable=protected-access
                raise
            finally:
                self._tx_db, self._tx_depth = None, 0

    def read(self, name: str) -> Any:
        """A deep copy of one doc, safe to use outside the lock."""
        with self.lock:
            return copy.deepcopy(self._docs[name])

    # ----- reset (DELETE /account) -----

    def wipe(self) -> None:
        """Deletes everything in the data dir except .gitignore; resets every doc to its default."""
        with self.lock:
            for entry in self.data_dir.iterdir():
                if entry.name == GITIGNORE:
                    continue
                try:
                    if entry.is_dir() and not entry.is_symlink():
                        shutil.rmtree(entry)
                    else:
                        entry.unlink()
                except OSError:
                    log.warning("Couldn't delete %s from the data dir", entry.name, exc_info=True)
            self._docs = {name: factory() for name, factory in DOC_DEFAULTS.items()}
            self._ensure_gitignore()

    # ----- loading -----

    def _ensure_gitignore(self) -> None:
        marker = self.path(GITIGNORE)
        if not marker.exists():
            marker.write_text("# Created by the AutoApply server: keep local data out of git.\n*\n",
                              encoding="utf-8")

    def _load(self, name: str) -> Any:
        default = DOC_DEFAULTS[name]()
        path = self.doc_path(name)
        if not path.exists():
            return default
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            aside = path.with_name(f"{path.stem}.corrupt-{int(time.time())}.json")
            log.warning("%s is unreadable; moved it to %s and started from defaults",
                        path.name, aside.name)
            try:
                os.replace(path, aside)
            except OSError:
                pass
            return default
        if isinstance(default, dict) and isinstance(value, dict):
            value = DOC_MIGRATIONS.get(name, lambda doc: doc)(value)
            return {**default, **value}  # keys added in newer versions get their defaults
        if default is not None and type(value) is not type(default):
            log.warning("%s has the wrong shape; using defaults", path.name)
            return default
        return value


def get_store(request: Request) -> Store:
    """FastAPI dependency: the app's Store."""
    return request.app.state.store
