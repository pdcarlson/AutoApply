"""Starts the API server: `python -m server` from backend/ (127.0.0.1:8080 by default)."""
import asyncio
import logging
import sys

import uvicorn

from server.app import create_app
from server.config import load_config


def main() -> None:
    """Run the server until it is stopped."""
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if sys.platform == "win32":
        # Playwright's sync API starts Chromium as a subprocess, which needs the Proactor loop.
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    config = load_config()
    app = create_app(config=config, start_worker=True)
    logging.getLogger("server").info(
        "Data dir %s; SUBMIT_REAL_FORM=%s; Claude %s",
        config.data_dir, config.submit_real_form, "on" if config.claude_enabled else "off")
    # Never --reload or several workers: on Windows uvicorn then switches asyncio to the Selector
    # loop, and sync Playwright can't launch Chromium under it. One process per data folder, too.
    uvicorn.run(app, host=config.host, port=config.port, reload=False, workers=1)


if __name__ == "__main__":
    main()
