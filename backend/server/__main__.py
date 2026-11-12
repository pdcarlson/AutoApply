"""`python -m server` from backend/: the local API on 127.0.0.1:8080 (AUTOAPPLY_HOST/PORT).

Never run it with --reload or several workers on Windows: uvicorn then switches asyncio to the
Selector loop, and sync Playwright can't launch Chromium under it.
"""
import asyncio
import logging
import sys

import uvicorn

from server.app import create_app
from server.config import load_config


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if sys.platform == "win32":
        # Playwright's sync API starts Chromium as a subprocess, which needs the Proactor loop.
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    config = load_config()
    app = create_app(config=config, start_worker=True)
    logging.getLogger("server").info(
        "Data dir %s; SUBMIT_REAL_FORM=%s; FAKE_GREENHOUSE=%s; Claude %s",
        config.data_dir, config.submit_real_form, config.fake_greenhouse,
        "on" if config.claude_enabled else "off")
    uvicorn.run(app, host=config.host, port=config.port, reload=False, workers=1)


if __name__ == "__main__":
    main()
