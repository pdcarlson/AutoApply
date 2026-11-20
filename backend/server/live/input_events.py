"""Turns the live view's mouse, wheel, key and text events into browser (CDP) input commands."""
import math

# The client sends one JSON object per event, with `x` and `y` as fractions (0..1) of the
# picture's width and height, so it never needs the page's size:
#   {"type": "mouse", "action": "move" | "down" | "up", "x", "y", "button", "buttons",
#    "clickCount", "modifiers": {"alt", "ctrl", "meta", "shift": bool}}
#   {"type": "wheel", "x", "y", "deltaX", "deltaY", "modifiers"}
#   {"type": "key", "action": "down" | "up", "key", "code", "keyCode", "text", "repeat",
#    "modifiers"}
#   {"type": "text", "text"}   typed or pasted text, inserted at the cursor
MAX_TEXT = 20_000  # one pasted text
MAX_KEY_TEXT = 8
MAX_KEY_NAME = 32
MAX_CLICK_COUNT = 3
BUTTONS_MASK = 0x1F
KEY_CODE_MASK = 0xFFFF

MODIFIER_BITS = {"alt": 1, "ctrl": 2, "meta": 4, "shift": 8}
MOUSE_ACTIONS = {"move": "mouseMoved", "down": "mousePressed", "up": "mouseReleased"}
MOUSE_BUTTONS = ("none", "left", "middle", "right")
MOUSE_COMMAND = "Input.dispatchMouseEvent"


def modifier_mask(modifiers) -> int:
    """Return CDP's modifier bit field for {"ctrl": true, ...}."""
    if not isinstance(modifiers, dict):
        return 0
    return sum(bit for name, bit in MODIFIER_BITS.items() if modifiers.get(name))


def to_cdp(event, width: float, height: float) -> tuple[str, dict] | None:
    """Return the CDP (method, params) for one input event, or None to ignore it.

    `width` and `height` are the page's size in CSS pixels.
    """
    if not isinstance(event, dict):
        return None
    kind = event.get("type")
    if kind in ("mouse", "wheel"):
        return _pointer_command(event, width, height)
    if kind == "key":
        return _key_command(event)
    if kind == "text":
        text = str(event.get("text") or "")[:MAX_TEXT]
        return ("Input.insertText", {"text": text}) if text else None
    return None


def _number(value, default: float = 0.0) -> float:
    """Return `value` as a finite float, or `default`."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _fraction(value) -> float:
    """Return `value` as a number clamped to 0..1."""
    return min(1.0, max(0.0, _number(value)))


def _pointer_command(event: dict, width: float, height: float) -> tuple[str, dict] | None:
    """Return the CDP command for a mouse or wheel event, or None to ignore it."""
    params = {"x": round(_fraction(event.get("x")) * width, 2),
              "y": round(_fraction(event.get("y")) * height, 2),
              "modifiers": modifier_mask(event.get("modifiers"))}
    if event.get("type") == "wheel":
        params.update(type="mouseWheel", deltaX=_number(event.get("deltaX")),
                      deltaY=_number(event.get("deltaY")))
        return MOUSE_COMMAND, params
    action = MOUSE_ACTIONS.get(event.get("action"))
    button = event.get("button")
    if action is None or button not in MOUSE_BUTTONS:
        return None
    click_count = int(_number(event.get("clickCount")))
    params.update(type=action, button=button,
                  buttons=int(_number(event.get("buttons"))) & BUTTONS_MASK,
                  clickCount=min(MAX_CLICK_COUNT, max(0, click_count)))
    return MOUSE_COMMAND, params


def _key_command(event: dict) -> tuple[str, dict] | None:
    """Return the CDP command for a key event, or None to ignore it."""
    action = event.get("action")
    if action not in ("down", "up"):
        return None
    text = str(event.get("text") or "")[:MAX_KEY_TEXT] if action == "down" else ""
    key_code = int(_number(event.get("keyCode"))) & KEY_CODE_MASK
    # A key press with no text (an arrow, a shortcut) is a raw key, so the page doesn't type it.
    key_type = "keyUp" if action == "up" else "keyDown" if text else "rawKeyDown"
    params = {"type": key_type, "modifiers": modifier_mask(event.get("modifiers")),
              "key": str(event.get("key") or "")[:MAX_KEY_NAME],
              "code": str(event.get("code") or "")[:MAX_KEY_NAME],
              "windowsVirtualKeyCode": key_code, "nativeVirtualKeyCode": key_code,
              "autoRepeat": bool(event.get("repeat"))}
    if text:
        params.update(text=text, unmodifiedText=text)
    return "Input.dispatchKeyEvent", params
