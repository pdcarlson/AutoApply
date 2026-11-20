"""Streams pictures of one browser page over CDP, and sends the person's input to it."""
import asyncio
import base64
import json
from typing import AsyncIterator, Protocol

import httpx
import websockets

from agent.browser import PageAddress
from server.live.input_events import to_cdp

JPEG_QUALITY = 70
MAX_FRAME_WIDTH = 1920
MAX_FRAME_HEIGHT = 1920
CONNECT_TIMEOUT_S = 5.0
DEFAULT_PAGE_SIZE = (1280.0, 720.0)  # CSS pixels, until the first frame says otherwise
DETACHED_EVENTS = ("Target.detachedFromTarget", "Inspector.detached", "Inspector.targetCrashed")


class BrowserGone(Exception):
    """The browser (or its page) can't be reached, or stopped answering."""


class PageStream(Protocol):
    """Pictures of one browser page, and a way to act on it."""

    def frames(self) -> AsyncIterator[bytes]:
        """Yield JPEGs of the page, newest only, until BrowserGone is raised.

        A slow reader skips frames instead of falling behind.
        """

    async def send_input(self, event: dict) -> None:
        """Act on the page as one input event from the client says."""

    async def close(self) -> None:
        """Stop streaming and let go of the browser (which stays open)."""


async def browser_ws_url(endpoint: str) -> str:
    """Return the browser's CDP WebSocket URL for an `http://host:port` or `ws(s)://` endpoint."""
    if endpoint.startswith(("ws://", "wss://")):
        return endpoint
    try:
        async with httpx.AsyncClient(timeout=CONNECT_TIMEOUT_S) as http:
            reply = await http.get(endpoint.rstrip("/") + "/json/version")
            reply.raise_for_status()
            return reply.json()["webSocketDebuggerUrl"]
    except (httpx.HTTPError, KeyError, ValueError) as error:
        raise BrowserGone(f"No browser at {endpoint}: {error}") from error


class CdpPageStream:  # pylint: disable=too-many-instance-attributes  # CDP plumbing state
    """A PageStream over CDP: screencast frames out, Input.* commands in.

    It is one more CDP client of the browser, beside the Playwright that drives the run. It
    runs on the server's event loop, so the run's thread is never involved, and it only reads
    the screen and sends input, so the run is not disturbed.
    """

    def __init__(self, socket, session_id: str):
        self._socket = socket
        self._session_id = session_id
        self._next_id = 0
        self._replies: dict[int, asyncio.Future] = {}
        self._frame: bytes | None = None
        self._frame_ready = asyncio.Event()
        self._size = DEFAULT_PAGE_SIZE
        self._gone: BrowserGone | None = None
        self._reader = asyncio.create_task(self._read())

    @classmethod
    async def open(cls, page: PageAddress) -> "CdpPageStream":
        """Attach to `page` and start its screencast."""
        url = await browser_ws_url(page.endpoint)
        try:
            socket = await websockets.connect(url, max_size=None, open_timeout=CONNECT_TIMEOUT_S,
                                              ping_interval=None)
        except (OSError, asyncio.TimeoutError, websockets.WebSocketException) as error:
            raise BrowserGone(f"Couldn't reach the browser: {error}") from error
        stream = cls(socket, "")
        try:
            await stream._attach(page.target_id)
        except BaseException:
            await stream.close()
            raise
        return stream

    # ----- PageStream -----

    async def frames(self) -> AsyncIterator[bytes]:
        """Yield JPEGs of the page, newest only, until BrowserGone is raised."""
        while True:
            await self._frame_ready.wait()
            if self._gone is not None:
                raise self._gone
            self._frame_ready.clear()
            frame, self._frame = self._frame, None
            if frame is not None:
                yield frame

    async def send_input(self, event: dict) -> None:
        """Act on the page as one input event from the client says."""
        command = to_cdp(event, *self._size)
        if command is not None:
            await self._post(*command)

    async def close(self) -> None:
        """Stop streaming and let go of the browser (which stays open)."""
        self._reader.cancel()
        try:
            await self._socket.close()
        except (websockets.WebSocketException, OSError):
            pass  # already closed
        self._fail(BrowserGone("The live view was closed."))

    # ----- CDP plumbing -----

    async def _attach(self, target_id: str) -> None:
        """Attach to the page's target and start its screencast."""
        attached = await self._call("Target.attachToTarget",
                                    {"targetId": target_id, "flatten": True}, session="")
        self._session_id = attached["sessionId"]
        await self._call("Page.startScreencast", {
            "format": "jpeg", "quality": JPEG_QUALITY, "maxWidth": MAX_FRAME_WIDTH,
            "maxHeight": MAX_FRAME_HEIGHT, "everyNthFrame": 1})

    async def _post(self, method: str, params: dict | None = None,
                    session: str | None = None) -> int:
        """Send a command without waiting for its reply; return its id."""
        if self._gone is not None:
            raise self._gone
        self._next_id += 1
        message = {"id": self._next_id, "method": method, "params": params or {}}
        session = self._session_id if session is None else session
        if session:
            message["sessionId"] = session
        try:
            await self._socket.send(json.dumps(message))
        except websockets.WebSocketException as error:
            raise BrowserGone("The browser closed.") from error
        return self._next_id

    async def _call(self, method: str, params: dict | None = None,
                    session: str | None = None) -> dict:
        """Send a command and return its result."""
        reply = asyncio.get_running_loop().create_future()
        self._replies[await self._post(method, params, session)] = reply
        try:
            return await asyncio.wait_for(reply, CONNECT_TIMEOUT_S)
        except asyncio.TimeoutError as error:
            raise BrowserGone(f"The browser didn't answer {method}.") from error

    async def _read(self) -> None:
        """Route everything the browser sends: replies to their callers, frames to `frames`."""
        try:
            async for raw in self._socket:
                message = json.loads(raw)
                if "id" in message:
                    self._settle_reply(message)
                elif message.get("method") == "Page.screencastFrame":
                    await self._on_frame(message["params"])
                elif message.get("method") in DETACHED_EVENTS:
                    break
        except (websockets.WebSocketException, OSError, ValueError, BrowserGone):
            pass  # the browser went away; _fail below tells everyone waiting
        self._fail(BrowserGone("The browser closed."))

    def _settle_reply(self, message: dict) -> None:
        """Hand a command's reply (or error) to the caller waiting for it."""
        reply = self._replies.pop(message["id"], None)
        if reply is None or reply.done():
            return
        if "error" in message:
            reply.set_exception(BrowserGone(message["error"].get("message", "")))
        else:
            reply.set_result(message.get("result") or {})

    async def _on_frame(self, params: dict) -> None:
        """Keep the newest frame (and the page's size), then acknowledge it."""
        metadata = params.get("metadata") or {}
        if metadata.get("deviceWidth") and metadata.get("deviceHeight"):
            self._size = (float(metadata["deviceWidth"]), float(metadata["deviceHeight"]))
        self._frame = base64.b64decode(params["data"])
        self._frame_ready.set()
        # The browser sends the next frame only after this one is acknowledged.
        await self._post("Page.screencastFrameAck", {"sessionId": params["sessionId"]})

    def _fail(self, error: BrowserGone) -> None:
        """Mark the stream gone and wake everyone waiting on it."""
        if self._gone is None:
            self._gone = error
        for reply in self._replies.values():
            if not reply.done():
                reply.set_exception(self._gone)
        self._replies.clear()
        self._frame_ready.set()
