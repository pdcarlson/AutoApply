"""The live view: streams a job's browser to the web app and passes the person's input back.

Three parts, so each can change without the others:

- The wire protocol (WebSocket, GET /api/jobs/:id/live; see server.routes.live) is plain
  pictures and input events. It says nothing about Chromium or CDP:

      server -> client   binary message: one JPEG of the page as it looks now
      client -> server   text message, JSON, one of
          {"type": "mouse", "action": "move" | "down" | "up", "x": 0..1, "y": 0..1,
           "button": "none" | "left" | "middle" | "right", "buttons": int, "clickCount": int,
           "modifiers": {"alt", "ctrl", "meta", "shift": bool}}
          {"type": "wheel", "x": 0..1, "y": 0..1, "deltaX": px, "deltaY": px, "modifiers": {}}
          {"type": "key", "action": "down" | "up", "key": str, "code": str, "keyCode": int,
           "text": str, "repeat": bool, "modifiers": {}}
          {"type": "text", "text": str}      typed or pasted text, inserted at the cursor

  `x` and `y` are fractions of the picture's width and height, so the client never needs the
  page's size. Close codes: CLOSE_NO_BROWSER (the job has no open browser) and
  CLOSE_BROWSER_GONE (it went away while streaming).

- `PageStream` is the source of pictures and the sink for input. `CdpPageStream` is the one
  implementation: it attaches to the run's page through the browser's CDP endpoint (a
  PageAddress from agent.browser) next to Playwright, from the server's event loop, so the
  run's thread is never involved. The endpoint can be on this machine or another one. A different kind of source only has to offer the same three
  methods (`frames`, `send_input`, `close`).

- `LiveViews` is the registry of which job has an open browser, and where.
"""
import asyncio
import base64
import json
import logging
import threading
from typing import AsyncIterator, Protocol

import httpx
import websockets

from agent.browser import PageAddress

log = logging.getLogger(__name__)

CLOSE_NO_BROWSER = 4404
CLOSE_BROWSER_GONE = 4410

JPEG_QUALITY = 70
MAX_FRAME_WIDTH = 1920
MAX_FRAME_HEIGHT = 1920
CONNECT_TIMEOUT_S = 5.0
MAX_TEXT = 20_000  # one pasted text
MAX_CLICK_COUNT = 3

MODIFIER_BITS = {"alt": 1, "ctrl": 2, "meta": 4, "shift": 8}
MOUSE_ACTIONS = {"move": "mouseMoved", "down": "mousePressed", "up": "mouseReleased"}
MOUSE_BUTTONS = ("none", "left", "middle", "right")


class BrowserGone(Exception):
    """The browser (or its page) can't be reached, or stopped answering."""


# ----- input events -> CDP commands (pure) -----

def _number(value, default=0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number == number and abs(number) != float("inf") else default


def _fraction(value) -> float:
    return min(1.0, max(0.0, _number(value)))


def modifier_mask(modifiers) -> int:
    """{"ctrl": true, ...} -> CDP's modifier bit field."""
    if not isinstance(modifiers, dict):
        return 0
    return sum(bit for name, bit in MODIFIER_BITS.items() if modifiers.get(name))


def to_cdp(event, width: float, height: float) -> tuple[str, dict] | None:
    """The CDP (method, params) for one input event from the client, or None to ignore it.

    `width` and `height` are the page's size in CSS pixels; `x` and `y` are fractions of it.
    """
    if not isinstance(event, dict):
        return None
    kind = event.get("type")
    modifiers = modifier_mask(event.get("modifiers"))
    if kind in ("mouse", "wheel"):
        params = {"x": round(_fraction(event.get("x")) * width, 2),
                  "y": round(_fraction(event.get("y")) * height, 2), "modifiers": modifiers}
        if kind == "wheel":
            params.update(type="mouseWheel", deltaX=_number(event.get("deltaX")),
                          deltaY=_number(event.get("deltaY")))
            return "Input.dispatchMouseEvent", params
        action = MOUSE_ACTIONS.get(event.get("action"))
        button = event.get("button")
        if action is None or button not in MOUSE_BUTTONS:
            return None
        params.update(type=action, button=button,
                      buttons=int(_number(event.get("buttons"))) & 0x1F,
                      clickCount=min(MAX_CLICK_COUNT, max(0, int(_number(event.get("clickCount"))))))
        return "Input.dispatchMouseEvent", params
    if kind == "key":
        action = event.get("action")
        if action not in ("down", "up"):
            return None
        text = str(event.get("text") or "")[:8] if action == "down" else ""
        key_code = int(_number(event.get("keyCode"))) & 0xFFFF
        params = {"type": "keyUp" if action == "up" else "keyDown" if text else "rawKeyDown",
                  "modifiers": modifiers, "key": str(event.get("key") or "")[:32],
                  "code": str(event.get("code") or "")[:32],
                  "windowsVirtualKeyCode": key_code, "nativeVirtualKeyCode": key_code,
                  "autoRepeat": bool(event.get("repeat"))}
        if text:
            params.update(text=text, unmodifiedText=text)
        return "Input.dispatchKeyEvent", params
    if kind == "text":
        text = str(event.get("text") or "")[:MAX_TEXT]
        return ("Input.insertText", {"text": text}) if text else None
    return None


# ----- the stream -----

class PageStream(Protocol):
    """Pictures of one browser page, and a way to act on it."""

    def frames(self) -> AsyncIterator[bytes]:
        """JPEGs of the page, newest only: a slow reader skips frames instead of falling
        behind. Ends by raising BrowserGone when the browser goes away."""

    async def send_input(self, event: dict) -> None:
        """Acts on the page as one input event of the wire protocol says."""

    async def close(self) -> None:
        """Stops streaming and lets go of the browser (which stays open)."""


async def browser_ws_url(endpoint: str) -> str:
    """The browser's CDP WebSocket URL for an `http://host:port` or `ws(s)://` endpoint."""
    if endpoint.startswith(("ws://", "wss://")):
        return endpoint
    try:
        async with httpx.AsyncClient(timeout=CONNECT_TIMEOUT_S) as http:
            reply = await http.get(endpoint.rstrip("/") + "/json/version")
            reply.raise_for_status()
            return reply.json()["webSocketDebuggerUrl"]
    except (httpx.HTTPError, KeyError, ValueError) as error:
        raise BrowserGone(f"No browser at {endpoint}: {error}") from error


class CdpPageStream:  # pylint: disable=too-many-instance-attributes
    """A PageStream over CDP: screencast frames out, Input.* commands in.

    It is one more CDP client of the browser, beside the Playwright that drives the run, and it
    only reads the screen and sends input, so the run is not disturbed.
    """

    def __init__(self, socket, session_id: str):
        self._socket = socket
        self._session_id = session_id
        self._next_id = 0
        self._replies: dict[int, asyncio.Future] = {}
        self._frame: bytes | None = None
        self._frame_ready = asyncio.Event()
        self._size = (1280.0, 720.0)  # CSS pixels, corrected by the first frame
        self._gone: BrowserGone | None = None
        self._reader = asyncio.create_task(self._read())

    @classmethod
    async def open(cls, page: PageAddress) -> "CdpPageStream":
        """Attaches to `page` and starts its screencast."""
        url = await browser_ws_url(page.endpoint)
        try:
            socket = await websockets.connect(url, max_size=None, open_timeout=CONNECT_TIMEOUT_S,
                                              ping_interval=None)
        except (OSError, asyncio.TimeoutError, websockets.WebSocketException) as error:
            raise BrowserGone(f"Couldn't reach the browser: {error}") from error
        stream = cls(socket, "")
        try:
            attached = await stream._call("Target.attachToTarget",
                                          {"targetId": page.target_id, "flatten": True},
                                          session="")
            stream._session_id = attached["sessionId"]
            await stream._call("Page.startScreencast", {
                "format": "jpeg", "quality": JPEG_QUALITY, "maxWidth": MAX_FRAME_WIDTH,
                "maxHeight": MAX_FRAME_HEIGHT, "everyNthFrame": 1})
        except BaseException:
            await stream.close()
            raise
        return stream

    # ----- CDP plumbing -----

    async def _post(self, method: str, params: dict | None = None,
                    session: str | None = None) -> int:
        """Sends a command without waiting for its reply; returns its id."""
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
        """Sends a command and returns its result."""
        reply = asyncio.get_running_loop().create_future()
        self._replies[await self._post(method, params, session)] = reply
        try:
            return await asyncio.wait_for(reply, CONNECT_TIMEOUT_S)
        except asyncio.TimeoutError as error:
            raise BrowserGone(f"The browser didn't answer {method}.") from error

    async def _read(self) -> None:
        """Routes everything the browser sends: replies to their callers, frames to `frames`."""
        try:
            async for raw in self._socket:
                message = json.loads(raw)
                if "id" in message:
                    reply = self._replies.pop(message["id"], None)
                    if reply is not None and not reply.done():
                        if "error" in message:
                            reply.set_exception(BrowserGone(message["error"].get("message", "")))
                        else:
                            reply.set_result(message.get("result") or {})
                elif message.get("method") == "Page.screencastFrame":
                    await self._on_frame(message["params"])
                elif message.get("method") in ("Target.detachedFromTarget",
                                               "Inspector.detached", "Inspector.targetCrashed"):
                    break
        except (websockets.WebSocketException, OSError, ValueError):
            pass
        except BrowserGone:
            pass
        self._fail(BrowserGone("The browser closed."))

    async def _on_frame(self, params: dict) -> None:
        metadata = params.get("metadata") or {}
        if metadata.get("deviceWidth") and metadata.get("deviceHeight"):
            self._size = (float(metadata["deviceWidth"]), float(metadata["deviceHeight"]))
        self._frame = base64.b64decode(params["data"])
        self._frame_ready.set()
        # The browser sends the next frame only after this one is acknowledged.
        await self._post("Page.screencastFrameAck", {"sessionId": params["sessionId"]})

    def _fail(self, error: BrowserGone) -> None:
        if self._gone is None:
            self._gone = error
        for reply in self._replies.values():
            if not reply.done():
                reply.set_exception(self._gone)
        self._replies.clear()
        self._frame_ready.set()

    # ----- PageStream -----

    async def frames(self) -> AsyncIterator[bytes]:
        while True:
            await self._frame_ready.wait()
            if self._gone is not None:
                raise self._gone
            self._frame_ready.clear()
            frame, self._frame = self._frame, None
            if frame is not None:
                yield frame

    async def send_input(self, event: dict) -> None:
        command = to_cdp(event, *self._size)
        if command is not None:
            await self._post(*command)

    async def close(self) -> None:
        self._reader.cancel()
        try:
            await self._socket.close()
        except (websockets.WebSocketException, OSError):
            pass
        self._fail(BrowserGone("The live view was closed."))


# ----- which job has a browser -----

class LiveViews:
    """The open pages by job id: `owner` is whatever opened it, `page` its PageAddress.

    Thread-safe. `drop` only removes the entry of the owner that set it, so a run that ends
    late can't take away the browser of the run that replaced it.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._views: dict[str, tuple[object, PageAddress]] = {}

    def set(self, job_id: str, owner: object, page: PageAddress) -> None:
        with self._lock:
            self._views[job_id] = (owner, page)

    def drop(self, job_id: str, owner: object) -> bool:
        """True if `owner`'s entry was there and is now removed."""
        with self._lock:
            entry = self._views.get(job_id)
            if entry is None or entry[0] is not owner:
                return False
            del self._views[job_id]
            return True

    def page(self, job_id: str) -> PageAddress | None:
        with self._lock:
            entry = self._views.get(job_id)
            return entry[1] if entry else None

    async def open_stream(self, job_id: str) -> PageStream | None:
        """A stream of `job_id`'s browser, or None when it has none (or it is gone)."""
        page = self.page(job_id)
        if page is None:
            return None
        try:
            return await CdpPageStream.open(page)
        except BrowserGone as error:
            log.info("Job %s: no live view: %s", job_id, error)
            return None
