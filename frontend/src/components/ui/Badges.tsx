import type { ReactNode } from 'react';
import type { Tone } from '@/lib/jobStatus';
import { cx } from '@/lib/cx';
import styles from './Badges.module.css';

/** Status pill. teal = filled (done or moving), amber = dashed (needs you), red = outline. */
export function Chip({ tone, children }: { tone: Tone; children: ReactNode }) {
  return <span className={cx(styles.chip, styles[tone])}>{children}</span>;
}

export type DotTone = 'mark' | 'ink' | 'amber' | 'red' | 'none';

export function Dot({ tone }: { tone: DotTone }) {
  return <span className={cx(styles.dot, styles[`dot-${tone}`])} aria-hidden="true" />;
}

/** Small number badge, e.g. on nav items. `warn` is dashed. */
export function Count({ value, label, warn }: { value: number; label?: string; warn?: boolean }) {
  return (
    <span className={cx(styles.count, warn && styles.countWarn)} aria-label={label}>
      {value}
    </span>
  );
}

/** Quiet inline tag, e.g. "Only Acme" or "Saved today". */
export function MiniTag({ children, filled }: { children: ReactNode; filled?: boolean }) {
  return <span className={cx(styles.miniTag, filled && styles.miniFilled)}>{children}</span>;
}
