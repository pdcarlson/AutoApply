/** React state for a live browser view: connection status, control and picture shape. */
import { useEffect, useRef, useState } from 'react';
import { connectLiveBrowser } from './connectLiveBrowser';
import type { LiveStatus } from './liveSocket';

const DEFAULT_ASPECT_RATIO = 16 / 9;

/** Connects the returned canvas ref to `url`; `reconnect` starts a fresh connection. */
export function useLiveBrowser(url: string) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [status, setStatus] = useState<LiveStatus>('connecting');
  const [isControlling, setIsControlling] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [aspectRatio, setAspectRatio] = useState(DEFAULT_ASPECT_RATIO);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    return connectLiveBrowser(canvas, url, {
      onStatus: setStatus,
      onControlling: setIsControlling,
      onShape: setAspectRatio,
    });
  }, [url, attempt]);

  const reconnect = () => {
    setStatus('connecting');
    setAttempt((count) => count + 1);
  };

  return { canvasRef, status, isControlling, aspectRatio, reconnect };
}
