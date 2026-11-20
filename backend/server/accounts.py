"""Whose data a request works on: one Account (store, answer bank, agent worker) per user.

- AUTH_MODE=local: there is one account, "local", and its files sit directly in the data dir,
  exactly where they always were. Nothing checks who is asking.
- AUTH_MODE=clerk: every request carries a Clerk session token (server.clerk). The token's user
  id picks the account; its files live in `<data_dir>/users/<user id>/`. Accounts are created
  the first time a user shows up, and every account already on disk is loaded at startup so
  its queue keeps going after a restart.

Routes get what they need through the FastAPI dependencies here and `server.store.get_store`:

    def route(store: Store = Depends(get_store), worker = Depends(get_worker)): ...

All workers share `run_slots`, so at most MAX_CONCURRENT_RUNS browsers fill or submit at once
however many users there are.
"""
import logging
import re
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from starlette.requests import HTTPConnection

from server import jobs
from server.answer_bank import AnswerBank
from server.clerk import ClerkUsers, TokenVerifier, bearer_token, unauthenticated
from server.config import Config
from server.store import DEMO_USER, Store, default_profile

log = logging.getLogger(__name__)

LOCAL_USER_ID = DEMO_USER["id"]
USERS_DIR = "users"
# Clerk user ids look like `user_2abcDEF...`. Anything else never becomes a folder name.
USER_ID = re.compile(r"^[A-Za-z0-9_]{1,80}$")


@dataclass
class Account:
    """One user's services."""

    user_id: str
    store: Store
    bank: AnswerBank
    worker: object  # AgentWorker


class Accounts:
    """The accounts by user id. Thread-safe."""

    def __init__(self, config: Config, make_worker: Callable[[Store, AnswerBank], object],
                 verifier: TokenVerifier | None = None, clerk_users: ClerkUsers | None = None):
        self.config = config
        self.verifier = verifier
        self.clerk_users = clerk_users or ClerkUsers()
        self._make_worker = make_worker
        self._lock = threading.RLock()
        self._accounts: dict[str, Account] = {}
        self._running = False
        if self.multi_user:
            for folder in sorted(self._users_dir().glob("*")):
                if folder.is_dir() and USER_ID.match(folder.name):
                    self._open(folder.name)
        else:
            self._open(LOCAL_USER_ID)

    @property
    def multi_user(self) -> bool:
        return self.config.auth_mode == "clerk"

    @property
    def local(self) -> Account | None:
        """The one account of AUTH_MODE=local (None with real sign-in)."""
        return self._accounts.get(LOCAL_USER_ID) if not self.multi_user else None

    def all(self) -> list[Account]:
        with self._lock:
            return list(self._accounts.values())

    # ----- folders -----

    def _users_dir(self) -> Path:
        return Path(self.config.data_dir) / USERS_DIR

    def _folder(self, user_id: str) -> Path:
        return self._users_dir() / user_id if self.multi_user else Path(self.config.data_dir)

    # ----- opening and closing -----

    def _open(self, user_id: str) -> Account:
        """Loads (or creates) the account's files and builds its worker."""
        store = Store(self._folder(user_id))
        bank = AnswerBank(store)
        if self.config.seed_bank_from_profile and not self.multi_user:
            bank.seed_from_profile(self.config.profile_path)  # once per data dir
        with store.tx() as db:  # jobs a previous process left mid-run (spec 2.3)
            jobs.recover_after_restart(db, store.now())
        account = Account(user_id, store, bank, self._make_worker(store, bank))
        self._accounts[user_id] = account
        if self._running:
            account.worker.start()
        return account

    def get(self, user_id: str) -> Account:
        """The account for `user_id`, created (with the name and email Clerk has) if new."""
        if not USER_ID.match(user_id or ""):
            raise unauthenticated()
        with self._lock:
            account = self._accounts.get(user_id)
            if account is not None:
                return account
            is_new = not self._folder(user_id).exists()
            account = self._open(user_id)
        if is_new and self.multi_user:
            self._greet(account)
        return account

    def _greet(self, account: Account) -> None:
        """A new account starts with the person's own name and email, not the demo user's."""
        who = self.clerk_users.identity(account.user_id)
        with account.store.tx() as db:
            db.state["user"] = {"name": " ".join(filter(None, (who["firstName"], who["lastName"]))),
                                "email": who["email"]}
            if db.profile == default_profile():
                db.profile.update(firstName=who["firstName"], middleName="",
                                  lastName=who["lastName"], email=who["email"])
        log.info("New account %s", account.user_id)

    def forget(self, user_id: str) -> None:
        """DELETE /account with real sign-in: stops the worker, closes its browsers (nobody
        else can reach them), removes the folder and the Clerk user."""
        with self._lock:
            account = self._accounts.pop(user_id, None)
        if account is None:
            return
        account.worker.cancel_current()
        account.worker.stop()
        account.worker.close_forms()
        shutil.rmtree(account.store.data_dir, ignore_errors=True)
        self.clerk_users.delete(user_id)

    def start(self) -> None:
        with self._lock:
            self._running = True
            for account in self._accounts.values():
                account.worker.start()

    def stop(self) -> None:
        with self._lock:
            self._running = False
            accounts = list(self._accounts.values())
        for account in accounts:
            account.worker.stop()

    # ----- who is asking -----

    def of(self, connection: HTTPConnection, token: str | None = None) -> Account:
        """The account a request (or WebSocket) is for. Raises ApiError 401 when it isn't
        signed in. `token` is for sockets, which can't send an Authorization header."""
        if not self.multi_user:
            return self._accounts[LOCAL_USER_ID]
        cached = getattr(connection.state, "account", None)
        if cached is not None:
            return cached
        claims = self.verifier.verify(token or bearer_token(
            connection.headers.get("authorization")))
        account = self.get(str(claims.get("sub") or ""))
        connection.state.account = account
        return account


def get_account(request: HTTPConnection) -> Account:
    """FastAPI dependency: the signed-in user's Account."""
    return request.app.state.accounts.of(request)


def get_worker(request: HTTPConnection):
    """FastAPI dependency: the signed-in user's AgentWorker."""
    return get_account(request).worker


def get_bank(request: HTTPConnection) -> AnswerBank:
    """FastAPI dependency: the signed-in user's AnswerBank."""
    return get_account(request).bank
