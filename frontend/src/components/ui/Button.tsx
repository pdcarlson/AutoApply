import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { cx } from '@/lib/cx';
import { buttonClass, type ButtonStyle } from './classNames';
import { Spinner } from './Spinner';
import styles from './Button.module.css';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, ButtonStyle {
  /** Shows a spinner and disables the button. */
  loading?: boolean;
  loadingLabel?: ReactNode;
}

export function Button({
  variant,
  size,
  grow,
  loading = false,
  loadingLabel,
  className,
  disabled,
  children,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cx(buttonClass({ variant, size, grow }), className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? (
        <>
          <Spinner />
          {loadingLabel ?? children}
        </>
      ) : (
        children
      )}
    </button>
  );
}

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Accessible name; icon buttons have no visible text. */
  label: string;
  /** No border until hovered. */
  plain?: boolean;
  size?: 'md' | 'sm';
}

export function IconButton({
  label,
  plain = false,
  size = 'md',
  className,
  type = 'button',
  ...rest
}: IconButtonProps) {
  return (
    <button
      type={type}
      aria-label={label}
      title={label}
      className={cx(
        styles.iconBtn,
        plain && styles.plain,
        size === 'sm' && styles.iconSm,
        className,
      )}
      {...rest}
    />
  );
}

/** A button that looks like an inline link. */
export function LinkButton({
  className,
  small,
  type = 'button',
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { small?: boolean }) {
  return (
    <button
      type={type}
      className={cx(styles.linkBtn, small && styles.linkSmall, className)}
      {...rest}
    />
  );
}
