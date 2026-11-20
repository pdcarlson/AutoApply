/** A row of toggle chips that filters a list. */
import { cx } from '@/lib/cx';
import { Dot, type DotTone } from './Badges';
import styles from './FilterChips.module.css';

/** One chip: its key, its label, and an optional count and dot. */
export interface FilterOption<K extends string> {
  key: K;
  label: string;
  count?: number;
  dot?: DotTone | null;
}

interface FilterChipsProps<K extends string> {
  options: FilterOption<K>[];
  value: K;
  onChange: (key: K) => void;
  /** Accessible name for the group. */
  label: string;
}

/** Row of toggle chips that filter a list; exactly one is on. */
export function FilterChips<K extends string>({
  options,
  value,
  onChange,
  label,
}: FilterChipsProps<K>) {
  return (
    <div className={styles.filterChips} role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.key}
          type="button"
          className={cx(styles.filterChip, value === option.key && styles.on)}
          aria-pressed={value === option.key}
          onClick={() => onChange(option.key)}
        >
          {option.dot && <Dot tone={option.dot} />}
          {option.label}
          {option.count !== undefined && <span className={styles.countText}>{option.count}</span>}
        </button>
      ))}
    </div>
  );
}
