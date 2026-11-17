"""Where a run's browser comes from, and how something else can watch and drive it.

A run asks a browser source for a browser and gets back a `(browser, endpoint)` pair. `endpoint`
is the browser's Chrome DevTools Protocol (CDP) address, or "" when it has none. With the page's
target id it makes a `PageAddress`: anything that speaks CDP can attach to that page next to
Playwright (the web app's live view does, in server.live_view), from any thread or machine that
can reach the address.

- `LocalBrowser` launches Chromium on this machine with a DevTools port on 127.0.0.1.
- `RemoteBrowser` drives a Chromium that is already running somewhere else (a VM, a browser
  service) through its CDP address. Set BROWSER_CDP_URL to use it.

Both are used the same way, so moving the browser off this machine only changes which one the
run is given.
"""
import socket
from dataclasses import dataclass

LOOPBACK = "127.0.0.1"


@dataclass(frozen=True)
class PageAddress:
    """One open page: the CDP `endpoint` of its browser (`http://host:port`, or a `ws://` or
    `wss://` URL) and the page's CDP `target_id` in it."""

    endpoint: str
    target_id: str


def page_address(page, endpoint: str) -> PageAddress:
    """The address of a Playwright `page` in the browser at `endpoint`."""
    session = page.context.new_cdp_session(page)
    try:
        return PageAddress(endpoint, session.send("Target.getTargetInfo")["targetInfo"]["targetId"])
    finally:
        session.detach()


def free_port() -> int:
    """A TCP port nothing is listening on right now."""
    with socket.socket() as probe:
        probe.bind((LOOPBACK, 0))
        return probe.getsockname()[1]


@dataclass
class LocalBrowser:
    """Chromium launched on this machine. `expose` opens a DevTools port for the live view."""

    show: bool = False
    slow_mo: int = 0
    expose: bool = True

    def open(self, playwright):
        """Launches the browser. Returns (browser, endpoint)."""
        if not self.expose:
            return playwright.chromium.launch(headless=not self.show, slow_mo=self.slow_mo), ""
        port = free_port()
        browser = playwright.chromium.launch(
            headless=not self.show, slow_mo=self.slow_mo,
            # Chromium listens on loopback only, and refuses connections made by web pages.
            args=[f"--remote-debugging-port={port}"])
        return browser, f"http://{LOOPBACK}:{port}"


@dataclass
class RemoteBrowser:
    """A Chromium that already runs elsewhere, reached through its CDP address.

    `endpoint` is what the browser's host gives out: `http://host:port` or a `ws://`/`wss://`
    URL. Closing the returned browser disconnects from it and closes the pages the run opened.
    """

    endpoint: str
    slow_mo: int = 0

    def open(self, playwright):
        """Connects to the browser. Returns (browser, endpoint)."""
        browser = playwright.chromium.connect_over_cdp(self.endpoint, slow_mo=self.slow_mo)
        return browser, self.endpoint
