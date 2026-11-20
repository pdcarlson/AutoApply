/** The job's browser, live: the page the agent is filling, which the user can also use. */
import { Button } from '@/components/ui/Button';
import { cx } from '@/lib/cx';
import type { LiveStatus } from './liveSocket';
import { useLiveBrowser } from './useLiveBrowser';
import styles from './LiveBrowser.module.css';

const STATUS_LABELS: Record<LiveStatus, string> = {
  connecting: 'Connecting',
  live: 'Live',
  ended: 'Closed',
};

/** The line beside the status: what's shown, or how to take control once it's live. */
function hintFor(status: LiveStatus, isControlling: boolean, label: string) {
  if (status !== 'live') return label;
  return isControlling
    ? 'You’re typing in the page. Click outside it to stop.'
    : 'Click the page to scroll, click and type in it yourself.';
}

interface LiveBrowserProps {
  /** A job's `liveView.url`. */
  url: string;
  /** What the picture shows, e.g. "Acme application form". */
  label: string;
  className?: string;
}

/** Streams the job's browser and lets the user click, scroll and type in it. */
export function LiveBrowser({ url, label, className }: LiveBrowserProps) {
  const { canvasRef, status, isControlling, aspectRatio, reconnect } = useLiveBrowser(url);
  const isLive = status === 'live';

  return (
    <section className={cx(styles.frame, className)} aria-label="Live browser">
      <div className={styles.bar}>
        <span className={cx(styles.dot, isLive && styles.dotLive)} aria-hidden="true" />
        <b>{STATUS_LABELS[status]}</b>
        <span className={styles.hint}>{hintFor(status, isControlling, label)}</span>
      </div>
      <div className={styles.stage} style={{ aspectRatio }}>
        <canvas
          ref={canvasRef}
          className={cx(styles.canvas, isControlling && styles.controlling)}
          tabIndex={0}
          role="img"
          aria-label={`${label}, live`}
          width={1280}
          height={720}
        />
        {!isLive && (
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
