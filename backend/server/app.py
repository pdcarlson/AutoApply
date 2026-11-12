"""The FastAPI app factory.

Extension points for later packages:

- Routes: add a module with `router = APIRouter()` to `server/routes/` and list it in
  `server.routes.ROUTE_MODULES`. Every router is mounted under `/api`. Path functions are plain
  `def` so they run in the threadpool (sync Playwright must not run on the event loop).
- Services: `_install_services()` puts shared objects on `app.state`:
    app.state.config       Config (server.config)
    app.state.store        Store  (server.store)
    app.state.answer_bank  AnswerBank (server.answer_bank) over <data_dir>/answer_bank.json
    app.state.worker       AgentWorker (server.worker); routes call `.wake()`, DELETE /account
                         calls `.cancel_current()`, tests call `.run_next()` directly
  The lifespan calls `worker.start()` when `start_worker` is true and `worker.stop()` on shutdown.
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server import jobs, konefal
from server.answer_bank import AnswerBank
from server.config import Config, load_config
from server.errors import install_error_handlers
from server.routes import ROUTE_MODULES
from server.store import Store
from server.worker import AgentWorker

log = logging.getLogger(__name__)

API_PREFIX = "/api"
CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


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

    def run_next(self) -> None:
        return None


def _install_services(app: FastAPI) -> None:
    """Builds the shared services on app.state. Later packages add theirs here, in order."""
    config: Config = app.state.config
    app.state.store = Store(config.data_dir)
    konefal.configure(config.data_dir)
    bank = AnswerBank(app.state.store)
    if config.seed_bank_from_profile:
        bank.seed_from_profile(config.profile_path)  # once per data dir; reads PROFILE_PATH only
    app.state.answer_bank = bank
    with app.state.store.tx() as db:  # jobs a previous process left mid-run (spec 2.3)
        jobs.recover_after_restart(db, app.state.store.now())
    app.state.worker = AgentWorker(app.state.store, bank, config)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    worker = app.state.worker
    if app.state.start_worker:
        worker.start()
    try:
        yield
    finally:
        worker.stop()


def create_app(data_dir: Path | str | None = None, start_worker: bool = True,
               config: Config | None = None) -> FastAPI:
    """Builds the app. `data_dir` overrides AUTOAPPLY_DATA_DIR; `config` replaces the env."""
    if config is None:
        config = load_config(data_dir)
    elif data_dir is not None:
        config.data_dir = Path(data_dir).resolve()

    app = FastAPI(
        title="AutoApply local API",
        lifespan=_lifespan,
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json",
    )
    app.state.config = config
    app.state.start_worker = start_worker
    _install_services(app)

    install_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for module in ROUTE_MODULES:
        app.include_router(module.router, prefix=API_PREFIX)
    return app
