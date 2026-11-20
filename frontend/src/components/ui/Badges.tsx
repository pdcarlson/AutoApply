/** Small inline status marks: chips, dots, counts, and tags. */
import type { ReactNode } from 'react';
import { cx } from '@/lib/cx';
import type { Tone } from '@/lib/jobStatus';
import styles from './Badges.module.css';

interface ChipProps {
  tone: Tone;
  children: ReactNode;
}

/** Status pill. teal = filled (done or moving), amber = dashed (needs you), red = outline. */
export function Chip({ tone, children }: ChipProps) {
  return <span className={cx(styles.chip, styles[tone])}>{children}</span>;
}

/** The color of a Dot; `none` keeps its space without showing it. */
export type DotTone = 'mark' | 'ink' | 'amber' | 'red' | 'none';

interface DotProps {
  tone: DotTone;
}

/** A small decorative status dot. */
export function Dot({ tone }: DotProps) {
  return <span className={cx(styles.dot, styles[`dot-${tone}`])} aria-hidden="true" />;
}

interface CountProps {
  value: number;
  /** Accessible name, e.g. "3 waiting". */
  label?: string;
  warn?: boolean;
}

/** Small number badge, e.g. on nav items. `warn` is dashed. */
export function Count({ value, label, warn }: CountProps) {
  return (
    <span className={cx(styles.count, warn && styles.countWarn)} aria-label={label}>
      {value}
    </span>
  );
}

interface MiniTagProps {
  children: ReactNode;
  filled?: boolean;
}

/** Quiet inline tag, e.g. "Only Acme" or "Saved today". */
export function MiniTag({ children, filled }: MiniTagProps) {
  return <span className={cx(styles.miniTag, filled && styles.miniFilled)}>{children}</span>;
}
