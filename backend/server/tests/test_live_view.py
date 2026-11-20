"""The live view: a job's browser streamed over WS /api/jobs/:id/live, and driven through it."""
import pytest
from starlette.websockets import WebSocketDisconnect

from agent.browser import RemoteBrowser
from server.live.input_events import modifier_mask, to_cdp
from server.live.live_views import LiveViews
from server.routes.live import CLOSE_FORBIDDEN, CLOSE_NO_BROWSER
from server.tests.job_helpers import (FAKE_URL, SECOND_URL, add_job, apply, job_detail,
                                      seed_fake_form_answers, set_up_profile, wait_until)

JPEG_MAGIC = b"\xff\xd8"


# ----- input events -> CDP -----

def test_mouse_positions_are_fractions_of_the_page():
    """Mouse x and y are fractions of the page, turned into CSS pixels."""
    method, params = to_cdp({"type": "mouse", "action": "down", "x": 0.5, "y": 0.25,
                             "button": "left", "buttons": 1, "clickCount": 2,
                             "modifiers": {"shift": True}}, 1280, 720)
    assert method == "Input.dispatchMouseEvent"
    assert params == {"type": "mousePressed", "x": 640, "y": 180, "button": "left", "buttons": 1,
                      "clickCount": 2, "modifiers": 8}


def test_positions_outside_the_picture_are_clamped():
    """A wheel event outside the picture is clamped to its edge."""
    _method, params = to_cdp({"type": "wheel", "x": 7, "y": -1, "deltaY": 120}, 1000, 500)
    assert (params["type"], params["x"], params["y"]) == ("mouseWheel", 1000, 0)
    assert (params["deltaX"], params["deltaY"]) == (0, 120)


def test_a_key_with_text_types_it_and_one_without_is_a_raw_key():
    """A key with text types it; one without is a raw key; key up never types."""
    _method, typed = to_cdp({"type": "key", "action": "down", "key": "a", "code": "KeyA",
                             "keyCode": 65, "text": "a"}, 1, 1)
    assert (typed["type"], typed["text"], typed["windowsVirtualKeyCode"]) == ("keyDown", "a", 65)
    _method, raw = to_cdp({"type": "key", "action": "down", "key": "a", "code": "KeyA",
                           "keyCode": 65, "modifiers": {"ctrl": True}}, 1, 1)
    assert (raw["type"], raw["modifiers"]) == ("rawKeyDown", 2) and "text" not in raw
    _method, released = to_cdp({"type": "key", "action": "up", "key": "a", "code": "KeyA",
                                "keyCode": 65, "text": "a"}, 1, 1)
    assert released["type"] == "keyUp" and "text" not in released


def test_pasted_text_is_inserted():
    """Pasted text is inserted at the cursor."""
    assert to_cdp({"type": "text", "text": "hello"}, 1, 1) == ("Input.insertText",
                                                                {"text": "hello"})


@pytest.mark.parametrize("event", [
    None, "click", {}, {"type": "nope"}, {"type": "text", "text": ""},
    {"type": "mouse", "action": "smash", "button": "left"},
    {"type": "mouse", "action": "down", "button": "fourth"},
    {"type": "key", "action": "hold", "key": "a"},
])
def test_anything_else_is_ignored(event):
    """Events that aren't part of the protocol are ignored."""
    assert to_cdp(event, 1280, 720) is None


def test_modifier_mask():
    """Each modifier key sets its own CDP bit."""
    assert modifier_mask({"alt": True, "ctrl": True, "meta": True, "shift": True}) == 15
    assert modifier_mask(None) == 0


def test_a_late_run_cannot_drop_the_view_of_the_run_that_replaced_it():
    """A run that ends late can't remove the view of the run that replaced it."""
    views, old, new = LiveViews(), object(), object()
    views.set("job-1", old, "old page")
    views.set("job-1", new, "new page")
    assert not views.drop("job-1", old)
    assert views.page("job-1") == "new page"
    assert views.drop("job-1", new) and views.page("job-1") is None


# ----- the socket, against a real browser -----

@pytest.fixture(name="ready_job")
def fixture_ready_job(client, app):
    """A fake-form job filled to `ready`, its browser still open; returns its id."""
    set_up_profile(client)
    seed_fake_form_answers(app)
    job = add_job(client, FAKE_URL)
    apply(client, job["id"])
    assert app.state.worker.run_next() == job["id"]
    assert job_detail(client, job["id"])["state"] == "ready"
    return job["id"]


def on_page(app, job_id, function):
    """Runs function(page) on the held form's own thread."""
    return app.state.worker.forms.get(job_id).call(lambda held: function(held.page))


def test_a_job_without_a_browser_has_no_live_view(client):
    """A job with no open browser has no liveView, and its socket closes at once."""
    set_up_profile(client)
    job = add_job(client, FAKE_URL)
    assert job["liveView"] is None
    with client.websocket_connect(f"/api/jobs/{job['id']}/live") as socket:
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_bytes()
    assert closed.value.code == CLOSE_NO_BROWSER


def test_the_held_form_is_streamed_and_can_be_driven(client, app, ready_job):
    """The held form streams pictures, and mouse, keys, paste and wheel act on it."""
    live = job_detail(client, ready_job)["liveView"]
    assert live == {"url": f"/api/jobs/{ready_job}/live"}
    box = on_page(app, ready_job, lambda page: page.locator("#phone").bounding_box())
    size = on_page(app, ready_job, lambda page: page.viewport_size)
    spot = {"x": (box["x"] + box["width"] - 5) / size["width"],
            "y": (box["y"] + box["height"] / 2) / size["height"]}
    on_page(app, ready_job, lambda page: page.fill("#phone", ""))

    with client.websocket_connect(live["url"]) as socket:
        assert socket.receive_bytes().startswith(JPEG_MAGIC)
        socket.send_json({"type": "nonsense"})  # ignored, and the socket stays open
        socket.send_text("not json")
        for action, buttons in (("down", 1), ("up", 0)):
            socket.send_json({"type": "mouse", "action": action, "button": "left",
                              "buttons": buttons, "clickCount": 1, **spot})
        for key in "42":
            for action in ("down", "up"):
                socket.send_json({"type": "key", "action": action, "key": key,
                                  "code": f"Digit{key}", "keyCode": ord(key), "text": key})
        socket.send_json({"type": "text", "text": " pasted"})
        assert wait_until(lambda: on_page(app, ready_job, lambda page: page.input_value(
            "#phone")) == "42 pasted")
        # The page changed, so a new picture comes.
        assert socket.receive_bytes().startswith(JPEG_MAGIC)

        # The wheel scrolls the page.
        on_page(app, ready_job, lambda page: page.evaluate(
            "document.body.style.minHeight = '3000px'"))
        socket.send_json({"type": "wheel", "x": 0.5, "y": 0.5, "deltaX": 0, "deltaY": 400})
        assert wait_until(lambda: on_page(app, ready_job, lambda page: page.evaluate(
            "window.scrollY")) > 0)

    # Watching and typing didn't take the form away from the run.
    assert app.state.worker.forms.get(ready_job).call(lambda held: held.usable())


def test_other_sites_cannot_open_the_socket(client, ready_job):
    """Only the web app's own origin may open the socket."""
    with client.websocket_connect(f"/api/jobs/{ready_job}/live",
                                  headers={"origin": "https://evil.example"}) as socket:
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_bytes()
    assert closed.value.code == CLOSE_FORBIDDEN
    with client.websocket_connect(f"/api/jobs/{ready_job}/live",
                                  headers={"origin": "http://localhost:5173"}) as socket:
        assert socket.receive_bytes().startswith(JPEG_MAGIC)


def test_the_live_view_ends_with_the_browser(client, app, ready_job):
    """Once the browser closes, the job has no live view and the socket closes."""
    app.state.worker.forms.get(ready_job).close()
    assert wait_until(lambda: job_detail(client, ready_job)["liveView"] is None)
    with client.websocket_connect(f"/api/jobs/{ready_job}/live") as socket:
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_bytes()
    assert closed.value.code == CLOSE_NO_BROWSER


def test_a_restart_clears_the_live_view(client, ready_job, make_app):
    """After a restart no job has a live view: the browsers ended with the old process."""
    assert job_detail(client, ready_job)["liveView"]
    restarted = make_app()
    with restarted.state.store.tx() as db:
        assert all(not job["internal"].get("liveView") for job in db.jobs)


def test_a_browser_running_elsewhere_is_driven_and_streamed(client, app, ready_job):
    """BROWSER_CDP_URL: the run connects to an already running Chromium instead of launching
    one, and the live view streams that one. The first job's browser stands in for it."""
    endpoint = app.state.worker.live.page(ready_job).endpoint
    app.state.config.browser_cdp_url = endpoint
    assert isinstance(app.state.worker.setup.browser_source(), RemoteBrowser)
    second = add_job(client, SECOND_URL)
    apply(client, second["id"])
    assert app.state.worker.run_next() == second["id"]
    assert job_detail(client, second["id"])["state"] == "ready"

    first_page = app.state.worker.live.page(ready_job)
    second_page = app.state.worker.live.page(second["id"])
    assert second_page.endpoint == endpoint and second_page.target_id != first_page.target_id
    with client.websocket_connect(f"/api/jobs/{second['id']}/live") as socket:
        assert socket.receive_bytes().startswith(JPEG_MAGIC)
