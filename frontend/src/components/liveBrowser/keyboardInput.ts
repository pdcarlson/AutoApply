/** Sends keys and pasted text on the live view's canvas to the job's browser. */
import { isPaste, keyInput, type LiveInput } from './protocol';

/** Forwards keys and pastes while `isControlling()` is true. Returns cleanup. */
export function attachKeyboardInput(
  canvas: HTMLCanvasElement,
  send: (input: LiveInput) => void,
  isControlling: () => boolean,
) {
  const keyHandler = (action: 'down' | 'up') => (event: KeyboardEvent) => {
    if (!isControlling() || isPaste(event)) return;
    event.preventDefault();
    event.stopPropagation(); // Escape belongs to the page, not to the dialog around it
    send(keyInput(action, event));
  };
  const handleKeyDown = keyHandler('down');
  const handleKeyUp = keyHandler('up');
  const handlePaste = (event: ClipboardEvent) => {
    if (!isControlling()) return;
    event.preventDefault();
    const text = event.clipboardData?.getData('text/plain');
    if (text) send({ type: 'text', text });
  };

  canvas.addEventListener('keydown', handleKeyDown);
  canvas.addEventListener('keyup', handleKeyUp);
  canvas.addEventListener('paste', handlePaste);

  return () => {
    canvas.removeEventListener('keydown', handleKeyDown);
    canvas.removeEventListener('keyup', handleKeyUp);
    canvas.removeEventListener('paste', handlePaste);
  };
}
