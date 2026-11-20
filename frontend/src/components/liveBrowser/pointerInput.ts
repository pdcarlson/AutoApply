/** Sends mouse and wheel events on the live view's canvas to the job's browser. */
import {
  buttonOf,
  modifiersOf,
  pictureBox,
  pointIn,
  wheelPixels,
  type LiveInput,
} from './protocol';

type MouseAction = 'move' | 'down' | 'up';

/** Listens for pointer input on `canvas`; `onPress` runs on every mouse down. Returns cleanup. */
export function attachPointerInput(
  canvas: HTMLCanvasElement,
  send: (input: LiveInput) => void,
  onPress: () => void,
) {
  let buttonsDown = 0;
  let queuedMove: MouseEvent | null = null;
  let moveFrame = 0;

  const box = () => pictureBox(canvas.getBoundingClientRect(), canvas.width, canvas.height);
  const sendMouse = (action: MouseAction, event: MouseEvent) =>
    send({
      type: 'mouse',
      action,
      ...pointIn(box(), event.clientX, event.clientY),
      button: action === 'move' ? 'none' : buttonOf(event.button),
      buttons: event.buttons,
      clickCount: action === 'move' ? 0 : Math.max(1, event.detail),
      modifiers: modifiersOf(event),
    });

  // Moves are sent at most once per animation frame.
  const queueMove = (event: MouseEvent) => {
    queuedMove = event;
    if (moveFrame) return;
    moveFrame = requestAnimationFrame(() => {
      moveFrame = 0;
      flushMove();
    });
  };
  const flushMove = () => {
    if (queuedMove) sendMouse('move', queuedMove);
    queuedMove = null;
  };

  // While a button is down, the window hears the mouse, so a drag can leave the picture.
  const handleWindowMove = (event: MouseEvent) => queueMove(event);
  const handleWindowUp = (event: MouseEvent) => {
    flushMove();
    sendMouse('up', event);
    buttonsDown = event.buttons;
    if (!buttonsDown) stopWatchingWindow();
  };
  const stopWatchingWindow = () => {
    window.removeEventListener('mousemove', handleWindowMove);
    window.removeEventListener('mouseup', handleWindowUp);
  };

  const handleDown = (event: MouseEvent) => {
    event.preventDefault();
    onPress();
    flushMove();
    if (!buttonsDown) {
      window.addEventListener('mousemove', handleWindowMove);
      window.addEventListener('mouseup', handleWindowUp);
    }
    buttonsDown = event.buttons;
    sendMouse('down', event);
  };
  const handleHover = (event: MouseEvent) => {
    if (!buttonsDown) queueMove(event);
  };
  const handleWheel = (event: WheelEvent) => {
    event.preventDefault();
    const { width, height } = box();
    const scale = canvas.width ? width / canvas.width : 1;
    send({
      type: 'wheel',
      ...pointIn(box(), event.clientX, event.clientY),
      deltaX: wheelPixels(event.deltaX, event.deltaMode, width, scale),
      deltaY: wheelPixels(event.deltaY, event.deltaMode, height, scale),
      modifiers: modifiersOf(event),
    });
  };
  const handleContextMenu = (event: Event) => event.preventDefault();

  canvas.addEventListener('mousedown', handleDown);
  canvas.addEventListener('mousemove', handleHover);
  canvas.addEventListener('wheel', handleWheel, { passive: false });
  canvas.addEventListener('contextmenu', handleContextMenu);

  return () => {
    cancelAnimationFrame(moveFrame);
    canvas.removeEventListener('mousedown', handleDown);
    canvas.removeEventListener('mousemove', handleHover);
    canvas.removeEventListener('wheel', handleWheel);
    canvas.removeEventListener('contextmenu', handleContextMenu);
    stopWatchingWindow();
  };
}
