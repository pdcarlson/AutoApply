"""JSON-document storage for one user's data folder, guarded by one lock."""
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

from server.json_file import atomic_write_text, dump_json
from server.store_docs import DOC_DEFAULTS, DOC_MIGRATIONS

__all__ = ["Db", "Store", "get_store", "iso", "new_id", "parse_iso", "utc_now"]

log = logging.getLogger(__name__)

GITIGNORE = ".gitignore"


def new_id(prefix: str) -> str:
    """Return a new random id, `<prefix>-<8 hex>`: new_id("a") -> "a-1f2e3d4c"."""
    return f"{prefix}-{secrets.token_hex(4)}"


def utc_now() -> datetime:
    """Return the current time in UTC."""
    return datetime.now(timezone.utc)


def iso(moment: datetime) -> str:
    """Return the moment as ISO 8601 in UTC with whole seconds: 2026-10-20T13:41:00Z."""
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(text: str | None) -> datetime | None:
    """Return the moment an ISO 8601 string names (UTC if it has no zone), or None."""
    if not text:
        return None
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


class Db:
    """The view a `store.tx()` block works on: `db.<doc name>` is the live in-memory doc.

    Reading a doc snapshots it; on exit only docs whose JSON changed are saved. Assigning
    `db.jobs = [...]` replaces a doc.
    """

    def __init__(self, store: "Store"):
        object.__setattr__(self, "_store", store)
        object.__setattr__(self, "_snapshots", {})

    def _touch(self, name: str) -> None:
        """Snapshot a doc the first time the block uses it."""
        if name not in DOC_DEFAULTS:
            raise AttributeError(f"Unknown store doc {name!r}")
        if name not in self._snapshots:
            self._snapshots[name] = dump_json(self._store._docs[name])  # pylint: disable=protected-access

    def __getattr__(self, name: str) -> Any:
        """Return the live doc called `name`."""
        if name.startswith("_"):
            raise AttributeError(name)
        self._touch(name)
        return self._store._docs[name]  # pylint: disable=protected-access

    def __setattr__(self, name: str, value: Any) -> None:
        """Replace the doc called `name`."""
        self._touch(name)
        self._store._docs[name] = value  # pylint: disable=protected-access

    def _changed(self) -> list[tuple[str, str]]:
        """Return (name, new JSON) for each touched doc that changed; raise if one isn't JSON."""
        docs = self._store._docs  # pylint: disable=protected-access
        out = []
        for name, before in self._snapshots.items():
            after = dump_json(docs[name])
            if after != before:
                out.append((name, after))
        return out

    def _rollback(self) -> None:
        """Put every touched doc back the way it was before the block."""
        docs = self._store._docs  # pylint: disable=protected-access
        for name, before in self._snapshots.items():
            docs[name] = json.loads(before)


class Store:
    """All JSON docs of one data folder, guarded by one RLock.

    Every doc in DOC_DEFAULTS lives in memory and in `<data_dir>/<name>.json`; changed docs are
    written atomically when a `tx()` block exits cleanly. One process per data folder: there is
    no lock across processes. The answer bank file isn't a doc, but callers hold `lock` for it.
    """

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
        """Return the current time (UTC, timezone-aware); tests can pass a fake `clock`."""
        return self.clock()

    def now_iso(self) -> str:
        """Return the current time as an ISO 8601 string."""
        return iso(self.now())

    # ----- paths -----

    def path(self, *parts: str) -> Path:
        """Return a path inside the data folder (not created)."""
        return self.data_dir.joinpath(*parts)

    def dir(self, *parts: str) -> Path:
        """Return a folder inside the data folder, created if needed: store.dir("screenshots")."""
        target = self.path(*parts)
        target.mkdir(parents=True, exist_ok=True)
        return target

    def doc_path(self, name: str) -> Path:
        """Return the file a doc is saved in."""
        return self.path(f"{name}.json")

    # ----- transactions -----

    @contextmanager
    def tx(self) -> Iterator[Db]:
        """Hold the lock for `with store.tx() as db:` and save changed docs on a clean exit.

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
        """Return a deep copy of one doc, safe to use outside the lock."""
        with self.lock:
            return copy.deepcopy(self._docs[name])

    # ----- reset (DELETE /account) -----

    def wipe(self) -> None:
        """Delete everything in the data folder but .gitignore and reset every doc."""
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
        """Keep the data folder out of git."""
        marker = self.path(GITIGNORE)
        if not marker.exists():
            marker.write_text("# Created by the AutoApply server: keep local data out of git.\n*\n",
                              encoding="utf-8")

    def _load(self, name: str) -> Any:
        """Return a doc from its file, upgraded, or its default if missing or unreadable."""
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
        if default is not None and type(value) is not type(default):
            log.warning("%s has the wrong shape; using defaults", path.name)
            return default
        value = DOC_MIGRATIONS.get(name, lambda doc: doc)(value)
        if isinstance(default, dict):
            return {**default, **value}  # keys added in newer versions get their defaults
        return value


def get_store(request: Request) -> Store:
    """Return the signed-in user's Store (a FastAPI dependency)."""
    return request.app.state.accounts.of(request).store
