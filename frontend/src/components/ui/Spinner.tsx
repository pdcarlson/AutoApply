/** A small spinning loading indicator. */
import styles from './Spinner.module.css';

interface SpinnerProps {
  /** Announces the spinner as a status; without it the spinner is decorative. */
  label?: string;
}

/** A spinner that sits inline with text. */
export function Spinner({ label }: SpinnerProps) {
  return (
    <span
      className={styles.spinner}
      role={label ? 'status' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    />
  );
}
