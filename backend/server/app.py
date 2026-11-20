"""The FastAPI app factory.

Extension points for later packages:

- Routes: add a module with `router = APIRouter()` to `server/routes/` and list it in
  `server.routes.ROUTE_MODULES`. Every router is mounted under `/api`. Path functions are plain
  `def` so they run in the threadpool (sync Playwright must not run on the event loop).
- Services: `_install_services()` puts shared objects on `app.state`:
    app.state.config       Config (server.config)
    app.state.accounts     Accounts (server.accounts): each user's Store, AnswerBank and
                         AgentWorker. Routes reach them with the dependencies `get_store`,
                         `get_bank` and `get_worker`, never through app.state.
  With AUTH_MODE=local there is one account, also reachable (for tests and scripts) as
    app.state.store        Store  (server.store)
    app.state.answer_bank  AnswerBank (server.answer_bank) over <data_dir>/answer_bank.json
    app.state.job_feed     JobFeed (agent.jobs.job_feed): the postings the job board ranks
    app.state.worker       AgentWorker (server.worker); routes call `.wake()`, DELETE /account
                         calls `.cancel_current()`, mark-submitted calls `.held_form(job_id)`,
                         tests call `.run_next()` directly, and the live view socket
                         (server.routes.live) reads `.live`, the open browsers by job id
  With AUTH_MODE=clerk those three are None: there is one of each per signed-in user.
  The lifespan starts every worker when `start_worker` is true and stops them on shutdown
  (which leaves the filled form windows alone: they end with the process).
"""
import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent.jobs.job_feed import JobFeed
from server import konefal
from server.accounts import Accounts
from server.agent_bridge import fake_boards
from server.clerk import ClerkUsers, TokenVerifier, issuer_from_publishable_key
from server.config import Config, load_config
from server.errors import install_error_handlers
from server.routes import ROUTE_MODULES
from server.worker import AgentWorker

log = logging.getLogger(__name__)

API_PREFIX = "/api"


class NullWorker:
    """A worker that does nothing: same interface as server.worker.AgentWorker."""

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def wake(self) -> None:
        pass

    def cancel_current(self) -> None:
        """Asks the run in progress (if any) to stop at the next field. Used by DELETE /account."""

    def held_form(self, job_id: str) -> None:  # pylint: disable=unused-argument
        """The session holding `job_id`'s filled window: there never is one."""
        return None

    def run_next(self) -> None:
        return None

    live = None  # no browsers, so no live views


def _install_services(app: FastAPI, verifier: TokenVerifier | None = None) -> None:
    """Builds the shared services on app.state. Later packages add theirs here, in order."""
    config: Config = app.state.config
    konefal.configure(config.data_dir)
    run_slots = threading.BoundedSemaphore(config.max_concurrent_runs)
    clerk_users = None
    if config.auth_mode == "clerk":
        if verifier is None:
            issuer = config.clerk_issuer or issuer_from_publishable_key(
                config.clerk_publishable_key)
            verifier = TokenVerifier(issuer, config.allowed_origins)
        clerk_users = ClerkUsers(config.clerk_secret_key)
    accounts = Accounts(
        config, lambda store, bank: AgentWorker(store, bank, config, run_slots=run_slots),
        verifier=verifier, clerk_users=clerk_users)
    app.state.accounts = accounts
    local = accounts.local
    app.state.store = local.store if local else None
    app.state.answer_bank = local.bank if local else None
    app.state.worker = local.worker if local else None
    # The job board's postings are public, so every user shares one feed. Each request ranks
    # them against that user's own profile. With FAKE_GREENHOUSE it never goes online.
    feed_path = config.data_dir / "job_feed.json"
    if config.fake_greenhouse:
        app.state.job_feed = JobFeed(feed_path, boards=fake_boards(), keep=None)
    else:
        app.state.job_feed = JobFeed(feed_path)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    accounts: Accounts = app.state.accounts
    if app.state.start_worker:
        accounts.start()
    try:
        yield
    finally:
        accounts.stop()


def create_app(data_dir: Path | str | None = None, start_worker: bool = True,
               config: Config | None = None, verifier: TokenVerifier | None = None) -> FastAPI:
    """Builds the app. `data_dir` overrides AUTOAPPLY_DATA_DIR; `config` replaces the env;
    `verifier` replaces the Clerk token check (tests sign their own tokens)."""
    if config is None:
        config = load_config(data_dir)
    elif data_dir is not None:
        config.data_dir = Path(data_dir).resolve()

    app = FastAPI(
        title="AutoApply API",
        lifespan=_lifespan,
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json",
    )
    app.state.config = config
    app.state.start_worker = start_worker
    app.state.live_origins = list(config.allowed_origins)  # may open the live view socket
    _install_services(app, verifier)

    install_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.allowed_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for module in ROUTE_MODULES:
        app.include_router(module.router, prefix=API_PREFIX)

    @app.get("/", include_in_schema=False)
    def root():
        """Someone opened the server's address in a browser: say what it is."""
        return {"service": "AutoApply API", "health": f"{API_PREFIX}/health",
                "note": "This is the API only. Open the AutoApply web app to use it."}
    return app
