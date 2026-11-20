"""Builds the FastAPI app: its services, error handlers, CORS and every router under /api."""
import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent.jobs.job_feed import JobFeed
from server import autoapply_modules
from server.accounts import Accounts
from server.agent_bridge import fake_boards
from server.clerk import ClerkUsers, TokenVerifier, issuer_from_publishable_key
from server.config import Config, load_config
from server.errors import install_error_handlers
from server.routes import ROUTE_MODULES
from server.runs.agent_worker import AgentWorker

log = logging.getLogger(__name__)

API_PREFIX = "/api"


def _install_services(app: FastAPI, verifier: TokenVerifier | None = None) -> None:
    """Put the shared services on app.state.

    Routes reach each user's Store, AnswerBank and worker through the `get_store`, `get_bank`
    and `get_worker` dependencies, never through app.state. With AUTH_MODE=local the one
    account's are also on app.state (store, answer_bank, worker) for tests and scripts; with
    AUTH_MODE=clerk those are None.
    """
    config: Config = app.state.config
    autoapply_modules.configure(config.data_dir)
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
    """Start every worker (when asked to) and stop them on shutdown.

    Stopping leaves the filled form windows alone: they end with the process.
    """
    accounts: Accounts = app.state.accounts
    if app.state.start_worker:
        accounts.start()
    try:
        yield
    finally:
        accounts.stop()


def create_app(data_dir: Path | str | None = None, start_worker: bool = True,
               config: Config | None = None, verifier: TokenVerifier | None = None) -> FastAPI:
    """Return a new app.

    `data_dir` overrides AUTOAPPLY_DATA_DIR, `config` replaces the environment and `verifier`
    replaces the Clerk token check (tests sign their own tokens). Path functions are plain `def`
    so they run in the threadpool: sync Playwright must not run on the event loop.
    """
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
