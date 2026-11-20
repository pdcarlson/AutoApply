/** A row of buttons where exactly one option is chosen. */
import { cx } from '@/lib/cx';
import styles from './Segmented.module.css';

/** An option given as its own label, or as a value with a separate label. */
type SegmentedOption<T extends string> = T | { value: T; label: string };

interface SegmentedProps<T extends string> {
  options: readonly SegmentedOption<T>[];
  value: T | null;
  onChange: (value: T) => void;
  labelledBy?: string;
  label?: string;
}

const optionParts = <T extends string>(option: SegmentedOption<T>) =>
  typeof option === 'string' ? { value: option, label: option } : option;

/** Row of mutually exclusive buttons, e.g. Yes / No. */
export function Segmented<T extends string>({
  options,
  value,
  onChange,
  labelledBy,
  label,
}: SegmentedProps<T>) {
  return (
    <div className={styles.seg} role="radiogroup" aria-labelledby={labelledBy} aria-label={label}>
      {options.map((option) => {
        const { value: optionValue, label: optionLabel } = optionParts(option);
        const isChosen = optionValue === value;
        return (
          <button
            key={optionValue}
            type="button"
            role="radio"
            aria-checked={isChosen}
            className={cx(styles.segBtn, isChosen && styles.on)}
            onClick={() => onChange(optionValue)}
          >
            {optionLabel}
          </button>
        );
      })}
    </div>
  );
}
