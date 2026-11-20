/** Wires a canvas to a job's live browser: pictures in, the user's input out. */
import { createFrameDrawer } from './frameDrawer';
import { attachKeyboardInput } from './keyboardInput';
import { openLiveSocket, type LiveStatus } from './liveSocket';
import { attachPointerInput } from './pointerInput';

/** What the live view reports back to its component. */
export interface LiveBrowserListeners {
  onStatus: (status: LiveStatus) => void;
  /** True while the user's keys go to the page. */
  onControlling: (isControlling: boolean) => void;
  onShape: (widthOverHeight: number) => void;
}

/**
 * Streams the picture at `url` into `canvas` and sends what the user does on it back.
 * Returns the cleanup.
 */
export function connectLiveBrowser(
  canvas: HTMLCanvasElement,
  url: string,
  { onStatus, onControlling, onShape }: LiveBrowserListeners,
) {
  // Keys only go to the page after a click on it, until focus leaves, so tabbing past the
  // picture never traps the keyboard.
  let isControlling = false;
  const setControlling = (value: boolean) => {
    if (isControlling === value) return;
    isControlling = value;
    onControlling(value);
  };

  const drawer = createFrameDrawer(canvas, onShape, () => socket.markLive());
  const socket = openLiveSocket(url, drawer.draw, onStatus);

  const detachPointer = attachPointerInput(canvas, socket.send, () => {
    canvas.focus({ preventScroll: true });
    setControlling(true);
  });
  const detachKeyboard = attachKeyboardInput(canvas, socket.send, () => isControlling);
  const handleBlur = () => setControlling(false);
  canvas.addEventListener('blur', handleBlur);

  return () => {
    drawer.stop();
    socket.close();
    detachPointer();
    detachKeyboard();
    canvas.removeEventListener('blur', handleBlur);
  };
}
