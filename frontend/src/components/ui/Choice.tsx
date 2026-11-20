/** A checkbox or radio button with its label. */
import type { InputHTMLAttributes, ReactNode } from 'react';
import { cx } from '@/lib/cx';
import styles from './Choice.module.css';

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
