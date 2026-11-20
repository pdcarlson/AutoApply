"""The live view socket: WS /jobs/{id}/live (the protocol is in server.live_view).

Pictures of the job's browser go out as binary messages; the person's mouse and keyboard come
back as JSON. The handler is async and never touches the store or Playwright: the stream talks
to the browser on its own.
"""
import asyncio
import json
import logging
from urllib.parse import urlsplit

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from server.errors import ApiError
from server.live_view import CLOSE_BROWSER_GONE, CLOSE_NO_BROWSER, BrowserGone, PageStream

router = APIRouter()
log = logging.getLogger(__name__)

CLOSE_FORBIDDEN = 4403
CLOSE_UNAUTHENTICATED = 4401
# A browser can't put an Authorization header on a WebSocket, so the web app sends the session
# token as a second subprotocol: `new WebSocket(url, [LIVE_PROTOCOL, token])`.
LIVE_PROTOCOL = "autoapply.live"


def offered_token(socket: WebSocket) -> tuple[str | None, str | None]:
    """(the subprotocol to accept, the session token) from Sec-WebSocket-Protocol."""
    offered = [part.strip() for part in
               (socket.headers.get("sec-websocket-protocol") or "").split(",") if part.strip()]
    if LIVE_PROTOCOL not in offered:
        return None, None
    token = next((part for part in offered if part != LIVE_PROTOCOL), None)
    return LIVE_PROTOCOL, token


def origin_allowed(socket: WebSocket, allowed: list[str]) -> bool:
    """Browsers don't apply CORS to WebSockets, so a page on another site could otherwise
    connect and drive the form. Only the web app's own origins may."""
    origin = socket.headers.get("origin")
    if not origin:
        return True  # not a browser page (scripts, tests)
    return origin in allowed or urlsplit(origin).netloc == socket.headers.get("host")


async def _send_frames(socket: WebSocket, stream: PageStream) -> None:
    async for frame in stream.frames():
        await socket.send_bytes(frame)


async def _receive_input(socket: WebSocket, stream: PageStream) -> None:
    while True:
        try:
            event = json.loads(await socket.receive_text())
        except ValueError:
            continue
        await stream.send_input(event)


@router.websocket("/jobs/{job_id}/live")
async def live_view(socket: WebSocket, job_id: str):
    protocol, token = offered_token(socket)
    await socket.accept(subprotocol=protocol)
    if not origin_allowed(socket, socket.app.state.live_origins):
        await socket.close(CLOSE_FORBIDDEN, "Not allowed from this origin.")
        return
    try:  # checking the token can read Clerk's keys over the network: off the event loop
        account = await asyncio.to_thread(socket.app.state.accounts.of, socket, token)
    except ApiError:
        await socket.close(CLOSE_UNAUTHENTICATED, "Sign in to continue.")
        return
    views = getattr(account.worker, "live", None)
    stream = await views.open_stream(job_id) if views is not None else None
    if stream is None:
        await socket.close(CLOSE_NO_BROWSER, "This job has no open browser.")
        return
    tasks = [asyncio.create_task(_send_frames(socket, stream)),
             asyncio.create_task(_receive_input(socket, stream))]
    try:
        done, _pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if any(isinstance(task.exception(), BrowserGone) for task in done
               if not task.cancelled()):
            await socket.close(CLOSE_BROWSER_GONE, "The browser closed.")
    except (WebSocketDisconnect, RuntimeError):
        pass  # the person left
    finally:
        for task in tasks:
            task.cancel()
        await stream.close()
