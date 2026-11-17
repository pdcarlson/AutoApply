/**
 * The live view's wire protocol (docs/api.md, "Live view"): JPEG pictures of the job's browser
 * come in as binary messages, and these input events go out as JSON. Positions are fractions of
 * the picture, so nothing here depends on the page's size or on how the browser is hosted.
 */

export interface Modifiers {
  alt: boolean;
  ctrl: boolean;
  meta: boolean;
  shift: boolean;
}

export type MouseButton = 'none' | 'left' | 'middle' | 'right';

export type LiveInput =
  | {
      type: 'mouse';
      action: 'move' | 'down' | 'up';
      x: number;
      y: number;
      button: MouseButton;
      buttons: number;
      clickCount: number;
      modifiers: Modifiers;
    }
  | { type: 'wheel'; x: number; y: number; deltaX: number; deltaY: number; modifiers: Modifiers }
  | {
      type: 'key';
      action: 'down' | 'up';
      key: string;
      code: string;
      keyCode: number;
      text: string;
      repeat: boolean;
      modifiers: Modifiers;
    }
  | { type: 'text'; text: string };

/** The job has no open browser (it closed, or the server restarted). */
export const CLOSE_NO_BROWSER = 4404;
/** The browser went away while streaming. */
export const CLOSE_BROWSER_GONE = 4410;
/** This page isn't allowed to open the socket. */
export const CLOSE_FORBIDDEN = 4403;

/** The WebSocket URL for a job's `liveView.url`, which may be a path, http(s) or ws(s). */
export function socketUrl(url: string, base: string): string {
  const full = new URL(url, base);
  if (full.protocol === 'http:') full.protocol = 'ws:';
  if (full.protocol === 'https:') full.protocol = 'wss:';
  return full.toString();
}

export interface Box {
  left: number;
  top: number;
  width: number;
  height: number;
}

/** Where a picture of the given size is drawn inside `frame` with `object-fit: contain`. */
export function pictureBox(frame: Box, pictureWidth: number, pictureHeight: number): Box {
  if (!pictureWidth || !pictureHeight || !frame.width || !frame.height) return frame;
  const scale = Math.min(frame.width / pictureWidth, frame.height / pictureHeight);
  const width = pictureWidth * scale;
  const height = pictureHeight * scale;
  return {
    left: frame.left + (frame.width - width) / 2,
    top: frame.top + (frame.height - height) / 2,
    width,
    height,
  };
}

const clamp = (value: number) => Math.min(1, Math.max(0, value));

/** A pointer position as fractions of the picture, clamped to its edges. */
export function pointIn(box: Box, clientX: number, clientY: number): { x: number; y: number } {
  return {
    x: box.width ? clamp((clientX - box.left) / box.width) : 0,
    y: box.height ? clamp((clientY - box.top) / box.height) : 0,
  };
}

type KeyLike = Pick<
  KeyboardEvent,
  'key' | 'code' | 'keyCode' | 'repeat' | 'altKey' | 'ctrlKey' | 'metaKey' | 'shiftKey'
> & { getModifierState?: (key: string) => boolean };

type ModifierKeys = Pick<KeyLike, 'altKey' | 'ctrlKey' | 'metaKey' | 'shiftKey'>;

export const modifiersOf = (event: ModifierKeys): Modifiers => ({
  alt: event.altKey,
  ctrl: event.ctrlKey,
  meta: event.metaKey,
  shift: event.shiftKey,
});

const MOUSE_BUTTONS: MouseButton[] = ['left', 'middle', 'right'];

export const buttonOf = (button: number): MouseButton => MOUSE_BUTTONS[button] ?? 'none';

/** Ctrl+V / Cmd+V: left to this page, whose `paste` event carries the clipboard text. */
export const isPaste = (event: KeyLike) =>
  (event.ctrlKey || event.metaKey) && !event.altKey && event.key.toLowerCase() === 'v';

/** The key event to send for a keydown or keyup, with the text a keydown types (if any). */
export function keyInput(action: 'down' | 'up', event: KeyLike): LiveInput {
  // AltGr shows up as Ctrl+Alt on Windows, but it types a character and is not a shortcut.
  const altGraph = event.getModifierState?.('AltGraph') ?? false;
  const modifiers = modifiersOf(event);
  if (altGraph) Object.assign(modifiers, { alt: false, ctrl: false });
  const shortcut = modifiers.alt || modifiers.ctrl || modifiers.meta;
  let text = '';
  if (action === 'down' && !shortcut) {
    if (event.key === 'Enter') text = '\r';
    else if ([...event.key].length === 1) text = event.key;
  }
  return {
    type: 'key',
    action,
    key: event.key,
    code: event.code,
    keyCode: event.keyCode,
    text,
    repeat: event.repeat,
    modifiers,
  };
}

const LINE_PIXELS = 16;

/** Wheel distance in pixels of the page, whatever unit the device reports and however the
 * picture is scaled on screen. */
export function wheelPixels(delta: number, deltaMode: number, pageSize: number, scale: number) {
  const pixels = deltaMode === 1 ? delta * LINE_PIXELS : deltaMode === 2 ? delta * pageSize : delta;
  return scale > 0 ? pixels / scale : pixels;
}
