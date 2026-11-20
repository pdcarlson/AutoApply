"""Whose data a request works on: one Account (store, answer bank, agent worker) per user."""
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
from server.store import Store
from server.store_docs import DEMO_USER, default_profile

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
    """The accounts by user id. Thread-safe.

    With AUTH_MODE=local there is one account, "local", whose files sit directly in the data
    folder and nothing checks who is asking. With AUTH_MODE=clerk the Clerk session token's user
    id picks the account, whose files live in `<data_dir>/users/<user id>/`; every account on
    disk is loaded at startup so its queue keeps going after a restart.
    """

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
        """Return True with real sign-in, where each user has an account of their own."""
        return self.config.auth_mode == "clerk"

    @property
    def local(self) -> Account | None:
        """Return the one account of AUTH_MODE=local, or None with real sign-in."""
        return self._accounts.get(LOCAL_USER_ID) if not self.multi_user else None

    def all(self) -> list[Account]:
        """Return every open account."""
        with self._lock:
            return list(self._accounts.values())

    # ----- folders -----

    def _users_dir(self) -> Path:
        """Return the folder that holds one folder per user."""
        return Path(self.config.data_dir) / USERS_DIR

    def _folder(self, user_id: str) -> Path:
        """Return the data folder of one user."""
        return self._users_dir() / user_id if self.multi_user else Path(self.config.data_dir)

    # ----- opening and closing -----

    def _open(self, user_id: str) -> Account:
        """Load (or create) the account's files and build its worker."""
        store = Store(self._folder(user_id))
        bank = AnswerBank(store)
        if self.config.seed_bank_from_profile and not self.multi_user:
            bank.seed_from_profile(self.config.profile_path)  # once per data dir
        with store.tx() as db:  # jobs a previous process left mid-run
            jobs.recover_after_restart(db, store.now())
        account = Account(user_id, store, bank, self._make_worker(store, bank))
        self._accounts[user_id] = account
        if self._running:
            account.worker.start()
        return account

    def get(self, user_id: str) -> Account:
        """Return the account for `user_id`, created (with Clerk's name and email) if new."""
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
        """Start a new account with the person's own name and email, not the demo user's."""
        who = self.clerk_users.identity(account.user_id)
        with account.store.tx() as db:
            db.state["user"] = {"name": " ".join(filter(None, (who["firstName"], who["lastName"]))),
                                "email": who["email"]}
            if db.profile == default_profile():
                db.profile.update(firstName=who["firstName"], middleName="",
                                  lastName=who["lastName"], email=who["email"])
        log.info("New account %s", account.user_id)

    def forget(self, user_id: str) -> None:
        """Remove an account for DELETE /account with real sign-in.

        Stops the worker, closes its browsers (nobody else can reach them), and removes the
        folder and the Clerk user.
        """
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
        """Start every account's worker, and each new account's from now on."""
        with self._lock:
            self._running = True
            for account in self._accounts.values():
                account.worker.start()

    def stop(self) -> None:
        """Stop every account's worker."""
        with self._lock:
            self._running = False
            accounts = list(self._accounts.values())
        for account in accounts:
            account.worker.stop()

    # ----- who is asking -----

    def of(self, connection: HTTPConnection, token: str | None = None) -> Account:
        """Return the account a request (or WebSocket) is for; raise ApiError 401 if signed out.

        `token` is for sockets, which can't send an Authorization header.
        """
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
    """Return the signed-in user's Account (a FastAPI dependency)."""
    return request.app.state.accounts.of(request)


def get_worker(request: HTTPConnection):
    """Return the signed-in user's AgentWorker (a FastAPI dependency)."""
    return get_account(request).worker


def get_bank(request: HTTPConnection) -> AnswerBank:
    """Return the signed-in user's AnswerBank (a FastAPI dependency)."""
    return get_account(request).bank
