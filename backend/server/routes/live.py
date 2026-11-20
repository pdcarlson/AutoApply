"""The live view socket, WS /jobs/:id/live: pictures of a job's browser out, input back in."""
import asyncio
import json
import logging
from urllib.parse import urlsplit

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from server.errors import ApiError
from server.live.page_stream import BrowserGone, PageStream

router = APIRouter()
log = logging.getLogger(__name__)

CLOSE_UNAUTHENTICATED = 4401
CLOSE_FORBIDDEN = 4403
CLOSE_NO_BROWSER = 4404  # the job has no open browser
CLOSE_BROWSER_GONE = 4410  # the browser went away while streaming
# A browser can't put an Authorization header on a WebSocket, so the web app sends the session
# token as a second subprotocol: `new WebSocket(url, [LIVE_PROTOCOL, token])`.
LIVE_PROTOCOL = "autoapply.live"


def offered_token(socket: WebSocket) -> tuple[str | None, str | None]:
    """Return (the subprotocol to accept, the session token) from Sec-WebSocket-Protocol."""
    offered = [part.strip() for part in
               (socket.headers.get("sec-websocket-protocol") or "").split(",") if part.strip()]
    if LIVE_PROTOCOL not in offered:
        return None, None
    token = next((part for part in offered if part != LIVE_PROTOCOL), None)
    return LIVE_PROTOCOL, token


def origin_allowed(socket: WebSocket, allowed: list[str]) -> bool:
    """Return True when the socket comes from the web app's own origin, or from no page.

    Browsers don't apply CORS to WebSockets, so a page on another site could otherwise connect
    and drive the form.
    """
    origin = socket.headers.get("origin")
    if not origin:
        return True  # not a browser page (scripts, tests)
    return origin in allowed or urlsplit(origin).netloc == socket.headers.get("host")


async def _send_frames(socket: WebSocket, stream: PageStream) -> None:
    """Send every picture of the page as a binary message."""
    async for frame in stream.frames():
        await socket.send_bytes(frame)


async def _receive_input(socket: WebSocket, stream: PageStream) -> None:
    """Pass each JSON input event from the client to the page; skip anything that isn't JSON."""
    while True:
        try:
            event = json.loads(await socket.receive_text())
        except ValueError:
            continue
        await stream.send_input(event)


async def _open_stream(socket: WebSocket, job_id: str) -> PageStream | None:
    """Check who is asking, then open the job's stream; close the socket and return None if not."""
    protocol, token = offered_token(socket)
    await socket.accept(subprotocol=protocol)
    if not origin_allowed(socket, socket.app.state.live_origins):
        await socket.close(CLOSE_FORBIDDEN, "Not allowed from this origin.")
        return None
    try:  # checking the token can read Clerk's keys over the network: off the event loop
        account = await asyncio.to_thread(socket.app.state.accounts.of, socket, token)
    except ApiError:
        await socket.close(CLOSE_UNAUTHENTICATED, "Sign in to continue.")
        return None
    views = getattr(account.worker, "live", None)
    stream = await views.open_stream(job_id) if views is not None else None
    if stream is None:
        await socket.close(CLOSE_NO_BROWSER, "This job has no open browser.")
    return stream


@router.websocket("/jobs/{job_id}/live")
async def live_view(socket: WebSocket, job_id: str):
    """Stream the job's browser until the person leaves or the browser goes away."""
    stream = await _open_stream(socket, job_id)
    if stream is None:
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
