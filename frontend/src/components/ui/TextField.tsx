/** A labeled single-line text input. */
import { useId, type InputHTMLAttributes, type ReactNode } from 'react';
import { cx } from '@/lib/cx';
import styles from './Form.module.css';

interface TextFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'onChange'> {
  label: ReactNode;
  value: string;
  onChange: (value: string) => void;
  hint?: ReactNode;
  className?: string;
}

/** Labeled single-line input. */
export function TextField({
  label,
  value,
  onChange,
  hint,
  className,
  id,
  ...rest
}: TextFieldProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  return (
    <div className={cx(styles.field, className)}>
      <label htmlFor={inputId}>{label}</label>
      <input
        id={inputId}
        className={styles.input}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        {...rest}
      />
      {hint && <span className="tiny muted">{hint}</span>}
    </div>
  );
}
