import { useEffect, useRef, useState } from 'react';
import { apiUrl } from '@/api/client';
import { Button } from '@/components/ui/Button';
import { cx } from '@/lib/cx';
import {
  buttonOf,
  CLOSE_BROWSER_GONE,
  CLOSE_FORBIDDEN,
  CLOSE_NO_BROWSER,
  isPaste,
  keyInput,
  modifiersOf,
  pictureBox,
  pointIn,
  socketUrl,
  wheelPixels,
  type LiveInput,
} from './protocol';
import styles from './LiveBrowser.module.css';

type Status = 'connecting' | 'live' | 'ended';

const RETRY_MS = 1000;
const MAX_RETRIES = 5;
const FINAL_CLOSE_CODES = [CLOSE_NO_BROWSER, CLOSE_BROWSER_GONE, CLOSE_FORBIDDEN];

/**
 * Streams the picture at `url` into `canvas` and sends what the person does on it back.
 * Returns the cleanup. Keys only go to the page after a click on it, until focus leaves, so
 * tabbing past the picture never traps the keyboard.
 */
function connect(
  canvas: HTMLCanvasElement,
  url: string,
  onStatus: (status: Status) => void,
  onControlling: (controlling: boolean) => void,
  onShape: (widthOverHeight: number) => void,
) {
  const context = canvas.getContext('2d');
  let socket: WebSocket | null = null;
  let stopped = false;
  let retries = 0;
  let retryTimer: ReturnType<typeof setTimeout> | undefined;
  let nextFrame: Blob | null = null;
  let drawing = false;
  let controlling = false;
  let buttonsDown = 0;
  let queuedMove: MouseEvent | null = null;
  let moveFrame = 0;

  const send = (input: LiveInput) => {
    if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(input));
  };

  // Draw the newest picture only: decoding is async, so older ones are skipped.
  const draw = async (frame: Blob) => {
    nextFrame = frame;
    if (drawing) return;
    drawing = true;
    while (nextFrame && !stopped) {
      const blob = nextFrame;
      nextFrame = null;
      try {
        const bitmap = await createImageBitmap(blob);
        if (canvas.width !== bitmap.width || canvas.height !== bitmap.height) {
          canvas.width = bitmap.width;
          canvas.height = bitmap.height;
          if (!stopped) onShape(bitmap.width / bitmap.height);
        }
        context?.drawImage(bitmap, 0, 0);
        bitmap.close();
        retries = 0;
        if (!stopped) onStatus('live');
      } catch {
        // A picture that can't be decoded is skipped; the next one replaces it.
      }
    }
    drawing = false;
  };

  const open = () => {
    socket = new WebSocket(socketUrl(url, apiUrl('/')));
    socket.binaryType = 'blob';
    socket.onmessage = (event) => {
      if (event.data instanceof Blob) void draw(event.data);
    };
    socket.onclose = (event) => {
      if (stopped) return;
      if (FINAL_CLOSE_CODES.includes(event.code) || retries >= MAX_RETRIES) {
        onStatus('ended');
        return;
      }
      retries += 1;
      onStatus('connecting');
      retryTimer = setTimeout(open, RETRY_MS);
    };
  };

  const box = () => pictureBox(canvas.getBoundingClientRect(), canvas.width, canvas.height);
  const mouse = (action: 'move' | 'down' | 'up', event: MouseEvent, button = event.button) =>
    send({
      type: 'mouse',
      action,
      ...pointIn(box(), event.clientX, event.clientY),
      button: action === 'move' ? 'none' : buttonOf(button),
      buttons: event.buttons,
      clickCount: action === 'move' ? 0 : Math.max(1, event.detail),
      modifiers: modifiersOf(event),
    });

  const setControlling = (value: boolean) => {
    if (controlling === value) return;
    controlling = value;
    onControlling(value);
  };

  // Moves are sent at most once per animation frame.
  const onMove = (event: MouseEvent) => {
    queuedMove = event;
    if (moveFrame) return;
    moveFrame = requestAnimationFrame(() => {
      moveFrame = 0;
      if (queuedMove) mouse('move', queuedMove);
      queuedMove = null;
    });
  };
  const flushMove = () => {
    if (queuedMove) mouse('move', queuedMove);
    queuedMove = null;
  };
  // While a button is down, the window hears the mouse, so a drag can leave the picture.
  const onWindowMove = (event: MouseEvent) => onMove(event);
  const onWindowUp = (event: MouseEvent) => {
    flushMove();
    mouse('up', event);
    buttonsDown = event.buttons;
    if (!buttonsDown) {
      window.removeEventListener('mousemove', onWindowMove);
      window.removeEventListener('mouseup', onWindowUp);
    }
  };
  const onDown = (event: MouseEvent) => {
    event.preventDefault();
    canvas.focus({ preventScroll: true });
    setControlling(true);
    flushMove();
    if (!buttonsDown) {
      window.addEventListener('mousemove', onWindowMove);
      window.addEventListener('mouseup', onWindowUp);
    }
    buttonsDown = event.buttons;
    mouse('down', event);
  };
  const onHover = (event: MouseEvent) => {
    if (!buttonsDown) onMove(event);
  };
  const onWheel = (event: WheelEvent) => {
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
  const onKey = (action: 'down' | 'up') => (event: KeyboardEvent) => {
    if (!controlling || isPaste(event)) return;
    event.preventDefault();
    event.stopPropagation(); // Escape belongs to the page, not to the dialog around it
    send(keyInput(action, event));
  };
  const onKeyDown = onKey('down');
  const onKeyUp = onKey('up');
  const onPaste = (event: ClipboardEvent) => {
    if (!controlling) return;
    event.preventDefault();
    const text = event.clipboardData?.getData('text/plain');
    if (text) send({ type: 'text', text });
  };
  const onBlur = () => setControlling(false);
  const onContextMenu = (event: Event) => event.preventDefault();

  canvas.addEventListener('mousedown', onDown);
  canvas.addEventListener('mousemove', onHover);
  canvas.addEventListener('wheel', onWheel, { passive: false });
  canvas.addEventListener('keydown', onKeyDown);
  canvas.addEventListener('keyup', onKeyUp);
  canvas.addEventListener('paste', onPaste);
  canvas.addEventListener('blur', onBlur);
  canvas.addEventListener('contextmenu', onContextMenu);
  open();

  return () => {
    stopped = true;
    clearTimeout(retryTimer);
    cancelAnimationFrame(moveFrame);
    socket?.close();
    canvas.removeEventListener('mousedown', onDown);
    canvas.removeEventListener('mousemove', onHover);
    canvas.removeEventListener('wheel', onWheel);
    canvas.removeEventListener('keydown', onKeyDown);
    canvas.removeEventListener('keyup', onKeyUp);
    canvas.removeEventListener('paste', onPaste);
    canvas.removeEventListener('blur', onBlur);
    canvas.removeEventListener('contextmenu', onContextMenu);
    window.removeEventListener('mousemove', onWindowMove);
    window.removeEventListener('mouseup', onWindowUp);
  };
}

interface LiveBrowserProps {
  /** A job's `liveView.url`. */
  url: string;
  /** What the picture shows, e.g. "Acme application form". */
  label: string;
  className?: string;
}

/**
 * The job's browser, live: the page the agent is filling, which the user can also click,
 * scroll and type in. It works the same wherever that browser runs.
 */
export function LiveBrowser({ url, label, className }: LiveBrowserProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [status, setStatus] = useState<Status>('connecting');
  const [controlling, setControlling] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [shape, setShape] = useState(16 / 9);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    return connect(canvas, url, setStatus, setControlling, setShape);
  }, [url, attempt]);

  const reconnect = () => {
    setStatus('connecting');
    setAttempt((count) => count + 1);
  };

  return (
    <section className={cx(styles.frame, className)} aria-label="Live browser">
      <div className={styles.bar}>
        <span className={cx(styles.dot, status === 'live' && styles.dotLive)} aria-hidden="true" />
        <b>{status === 'live' ? 'Live' : status === 'ended' ? 'Closed' : 'Connecting'}</b>
        <span className={styles.hint}>
          {status !== 'live'
            ? label
            : controlling
              ? 'You’re typing in the page. Click outside it to stop.'
              : 'Click the page to scroll, click and type in it yourself.'}
        </span>
      </div>
      <div className={styles.stage} style={{ aspectRatio: shape }}>
        <canvas
          ref={canvasRef}
          className={cx(styles.canvas, controlling && styles.controlling)}
          tabIndex={0}
          role="img"
          aria-label={`${label}, live`}
          width={1280}
          height={720}
        />
        {status !== 'live' && (
          <div className={styles.cover} role="status">
            {status === 'connecting' ? (
              <span>Connecting to the browser…</span>
            ) : (
              <>
                <span>The browser isn’t open anymore.</span>
                <Button size="sm" onClick={reconnect}>
                  Try again
                </Button>
              </>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
