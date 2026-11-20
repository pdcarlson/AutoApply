/** The live view's WebSocket: connects with a fresh token and retries a few times. */
import { authToken } from '@/api/authToken';
import { apiUrl } from '@/api/client';
import {
  CLOSE_BROWSER_GONE,
  CLOSE_FORBIDDEN,
  CLOSE_NO_BROWSER,
  LIVE_PROTOCOL,
  socketUrl,
  type LiveInput,
} from './protocol';

/** Where the live view's connection stands. */
export type LiveStatus = 'connecting' | 'live' | 'ended';

const RETRY_MS = 1000;
const MAX_RETRIES = 5;
const FINAL_CLOSE_CODES = [CLOSE_NO_BROWSER, CLOSE_BROWSER_GONE, CLOSE_FORBIDDEN];

/** An open live view connection. */
export interface LiveSocket {
  send: (input: LiveInput) => void;
  /** Called once a picture is on screen: resets the retry count and reports "live". */
  markLive: () => void;
  close: () => void;
}

/** Opens the socket for a job's `liveView.url` and hands each picture to `onFrame`. */
export function openLiveSocket(
  url: string,
  onFrame: (frame: Blob) => void,
  onStatus: (status: LiveStatus) => void,
): LiveSocket {
  let socket: WebSocket | null = null;
  let isStopped = false;
  let retries = 0;
  let retryTimer: ReturnType<typeof setTimeout> | undefined;

  const retryOrEnd = (closeCode?: number) => {
    if (isStopped) return;
    if ((closeCode && FINAL_CLOSE_CODES.includes(closeCode)) || retries >= MAX_RETRIES) {
      onStatus('ended');
      return;
    }
    retries += 1;
    onStatus('connecting');
    retryTimer = setTimeout(open, RETRY_MS);
  };

  // A fresh token for every (re)connection: they only live for a minute.
  function open() {
    authToken()
      .then((token) => {
        if (isStopped) return;
        socket = new WebSocket(
          socketUrl(url, apiUrl('/')),
          token ? [LIVE_PROTOCOL, token] : undefined,
        );
        socket.binaryType = 'blob';
        socket.onmessage = (event) => {
          if (event.data instanceof Blob) onFrame(event.data);
        };
        socket.onclose = (event) => retryOrEnd(event.code);
      })
      .catch(() => retryOrEnd());
  }

  open();

  return {
    send: (input) => {
      if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(input));
    },
    markLive: () => {
      retries = 0;
      if (!isStopped) onStatus('live');
    },
    close: () => {
      isStopped = true;
      clearTimeout(retryTimer);
      socket?.close();
    },
  };
}
