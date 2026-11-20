/** A horizontal bar showing how far along something is. */
import { cx } from '@/lib/cx';
import styles from './ProgressBar.module.css';

interface ProgressBarProps {
  /** 0–100. */
  value: number;
  thin?: boolean;
  /** Announces the bar as a progressbar; without it the bar is decorative. */
  label?: string;
  className?: string;
}

/** Progress from 0 to 100, clamped and rounded. */
export function ProgressBar({ value, thin, label, className }: ProgressBarProps) {
  const percent = Math.min(100, Math.max(0, Math.round(value)));
  return (
    <span
      className={cx(styles.bar, thin && styles.thin, className)}
      role={label ? 'progressbar' : undefined}
      aria-label={label}
      aria-valuenow={label ? percent : undefined}
      aria-valuemin={label ? 0 : undefined}
      aria-valuemax={label ? 100 : undefined}
    >
      <span style={{ width: `${percent}%` }} />
    </span>
  );
}
