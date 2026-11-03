import { useId, useState, type InputHTMLAttributes, type ReactNode } from 'react';
import { cx } from '@/lib/cx';
import { Icon } from './Icon';
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
        onChange={(e) => onChange(e.target.value)}
        {...rest}
      />
      {hint && <span className="tiny muted">{hint}</span>}
    </div>
  );
}

interface TextAreaFieldProps {
  label: ReactNode;
  value: string;
  onChange: (value: string) => void;
  rows?: number;
  placeholder?: string;
  hint?: ReactNode;
  className?: string;
}

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
        onChange={(e) => onChange(e.target.value)}
      />
      {hint && <span className="tiny muted">{hint}</span>}
    </div>
  );
}

interface ChoiceProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  type: 'checkbox' | 'radio';
  children: ReactNode;
}

/** A checkbox or radio with its label to the right. */
export function Choice({ type, children, className, ...rest }: ChoiceProps) {
  return (
    <label className={cx(type === 'radio' ? styles.radio : styles.check, className)}>
      <input type={type} {...rest} />
      {children}
    </label>
  );
}

interface SegmentedProps<T extends string> {
  options: readonly (T | { value: T; label: string })[];
  value: T | null;
  onChange: (value: T) => void;
  labelledBy?: string;
  label?: string;
}

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
        const { value: optionValue, label: optionLabel } =
          typeof option === 'string' ? { value: option, label: option } : option;
        const on = optionValue === value;
        return (
          <button
            key={optionValue}
            type="button"
            role="radio"
            aria-checked={on}
            className={cx(styles.segBtn, on && styles.on)}
            onClick={() => onChange(optionValue)}
          >
            {optionLabel}
          </button>
        );
      })}
    </div>
  );
}

interface PillInputProps {
  items: string[];
  onChange: (items: string[]) => void;
  label: string;
  addLabel: string;
  placeholder?: string;
}

/** Editable list of short values shown as pills, e.g. skills or places. */
export function PillInput({ items, onChange, label, addLabel, placeholder }: PillInputProps) {
  const [draft, setDraft] = useState<string | null>(null);

  const commit = () => {
    const value = (draft ?? '').trim();
    if (value && !items.includes(value)) onChange([...items, value]);
    setDraft(null);
  };

  return (
    <div className={styles.pills} role="group" aria-label={label}>
      {items.map((item) => (
        <span key={item} className={styles.pill}>
          {item}
          <button
            type="button"
            aria-label={`Remove ${item}`}
            onClick={() => onChange(items.filter((i) => i !== item))}
          >
            <Icon name="close" size={14} stroke={2} />
          </button>
        </span>
      ))}
      {draft === null ? (
        <button type="button" className={styles.pillAdd} onClick={() => setDraft('')}>
          + {addLabel}
        </button>
      ) : (
        <input
          className={styles.pillInput}
          aria-label={addLabel}
          placeholder={placeholder}
          value={draft}
          autoFocus
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              commit();
            } else if (e.key === 'Escape') {
              e.stopPropagation();
              setDraft(null);
            }
          }}
          onBlur={commit}
        />
      )}
    </div>
  );
}

interface DateInputProps {
  value: string;
  onChange: (value: string) => void;
  labelledBy?: string;
  id?: string;
  disabled?: boolean;
}

/** Native date picker with a calendar icon; clicking anywhere on it opens the picker. */
export function DateInput({ value, onChange, labelledBy, id, disabled }: DateInputProps) {
  return (
    <label
      className={styles.dateField}
      onClick={(e) => {
        const input = e.currentTarget.querySelector('input');
        try {
          input?.showPicker?.();
        } catch {
          // showPicker throws if the input isn't focusable yet; the native click still works.
        }
      }}
    >
      <Icon name="calendar" size={18} stroke={1.8} />
      <input
        id={id}
        type="date"
        className={cx(styles.input, styles.dateInput)}
        aria-labelledby={labelledBy}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}
