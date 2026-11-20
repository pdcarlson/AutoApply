/** What a list or screen shows while it loads, when it fails, or when it has nothing in it. */
import type { ReactNode } from 'react';
import { Spinner } from './Spinner';
import styles from './LoadStates.module.css';

interface EmptyProps {
  children: ReactNode;
}

/** Centered muted message for an empty list. */
export function Empty({ children }: EmptyProps) {
  return <p className={styles.empty}>{children}</p>;
}

interface LoadingProps {
  label?: string;
}

/** Placeholder while a query loads. */
export function Loading({ label = 'Loading…' }: LoadingProps) {
  return (
    <div className={styles.loading} role="status">
      <Spinner />
      <span>{label}</span>
    </div>
  );
}

interface LoadErrorProps {
  onRetry?: () => void;
  /** What failed to load, as in "We couldn't load {what}". */
  what?: string;
}

/** Shown in place of content whose query failed. */
export function LoadError({ onRetry, what = 'this' }: LoadErrorProps) {
  return (
    <div className={styles.loadError} role="alert">
      <span>We couldn’t load {what}. Check your connection and try again.</span>
      {onRetry && (
        <button type="button" className={styles.retry} onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}
