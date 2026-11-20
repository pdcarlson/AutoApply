/** A labeled multi-line text input. */
import { useId, type ReactNode } from 'react';
import { cx } from '@/lib/cx';
import styles from './Form.module.css';

interface TextAreaFieldProps {
  label: ReactNode;
  value: string;
  onChange: (value: string) => void;
  rows?: number;
  placeholder?: string;
  hint?: ReactNode;
  className?: string;
}

/** Labeled textarea. */
export function TextAreaField({
  label,
  value,
  onChange,
  rows = 4,
  placeholder,
  hint,
  className,
}: TextAreaFieldProps) {
  const id = useId();
  return (
    <div className={cx(styles.field, className)}>
      <label htmlFor={id}>{label}</label>
      <textarea
        id={id}
        className={cx(styles.input, styles.textarea)}
        rows={rows}
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
      {hint && <span className="tiny muted">{hint}</span>}
    </div>
  );
}
