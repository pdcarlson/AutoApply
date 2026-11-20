/** A native date picker with a calendar icon. */
import type { MouseEvent } from 'react';
import { cx } from '@/lib/cx';
import { Icon } from './Icon';
import formStyles from './Form.module.css';
import styles from './DateInput.module.css';

interface DateInputProps {
  value: string;
  onChange: (value: string) => void;
  labelledBy?: string;
  id?: string;
  disabled?: boolean;
}

/** Opens the browser's picker wherever the field is clicked, not only on the tiny icon. */
function openPicker(event: MouseEvent<HTMLLabelElement>) {
  const input = event.currentTarget.querySelector('input');
  try {
    input?.showPicker?.();
  } catch {
    // showPicker throws if the input isn't focusable yet; the native click still works.
  }
}

/** Native date picker with a calendar icon; clicking anywhere on it opens the picker. */
export function DateInput({ value, onChange, labelledBy, id, disabled }: DateInputProps) {
  return (
    <label className={styles.dateField} onClick={openPicker}>
      <Icon name="calendar" size={18} stroke={1.8} />
      <input
        id={id}
        type="date"
        className={cx(formStyles.input, styles.dateInput)}
        aria-labelledby={labelledBy}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}
