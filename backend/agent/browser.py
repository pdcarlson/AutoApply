"""Where a run's browser comes from, and the address other tools use to watch and drive it."""
import socket
import sys
from dataclasses import dataclass

LOOPBACK = "127.0.0.1"
# Containers give /dev/shm very little room, and Chromium crashes when it fills up: on Linux it
# keeps its shared memory in /tmp instead.
PLATFORM_ARGS = ("--disable-dev-shm-usage",) if sys.platform.startswith("linux") else ()


@dataclass(frozen=True)
class PageAddress:
    """One open page, which anything that speaks the Chrome DevTools Protocol can attach to.

    `endpoint` is its browser's CDP address (`http://host:port`, or a `ws://` or `wss://` URL)
    and `target_id` is the page's CDP target id in that browser.
    """

    endpoint: str
    target_id: str


def page_address(page, endpoint: str) -> PageAddress:
    """Return the address of a Playwright `page` in the browser at `endpoint`."""
    session = page.context.new_cdp_session(page)
    try:
        return PageAddress(endpoint, session.send("Target.getTargetInfo")["targetInfo"]["targetId"])
    finally:
        session.detach()


def free_port() -> int:
    """Return a TCP port nothing is listening on right now."""
    with socket.socket() as probe:
        probe.bind((LOOPBACK, 0))
        return probe.getsockname()[1]


@dataclass
class LocalBrowser:
    """Chromium launched on this machine. `expose` opens a DevTools port for the live view."""

    show: bool = False
    slow_mo: int = 0
    expose: bool = True

    def open(self, playwright) -> tuple:
        """Launch the browser, and return it with its CDP endpoint ("" when not exposed)."""
        if not self.expose:
            return playwright.chromium.launch(headless=not self.show, slow_mo=self.slow_mo,
                                              args=list(PLATFORM_ARGS)), ""
        port = free_port()
        browser = playwright.chromium.launch(
            headless=not self.show, slow_mo=self.slow_mo,
            # Chromium listens on loopback only, and refuses connections made by web pages.
            args=[*PLATFORM_ARGS, f"--remote-debugging-port={port}"])
        return browser, f"http://{LOOPBACK}:{port}"


@dataclass
class RemoteBrowser:
    """A Chromium that already runs elsewhere (a VM, a browser service), reached over CDP.

    `endpoint` is what the browser's host gives out: `http://host:port` or a `ws://`/`wss://`
    URL. Closing the returned browser disconnects from it and closes the pages the run opened.
    """

    endpoint: str
    slow_mo: int = 0

    def open(self, playwright) -> tuple:
        """Connect to the browser, and return it with its CDP endpoint."""
        browser = playwright.chromium.connect_over_cdp(self.endpoint, slow_mo=self.slow_mo)
        return browser, self.endpoint
