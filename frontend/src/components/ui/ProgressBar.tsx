import { cx } from '@/lib/cx';
import styles from './ProgressBar.module.css';

interface ProgressBarProps {
  /** 0–100. */
  value: number;
  thin?: boolean;
  label?: string;
  className?: string;
}

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
