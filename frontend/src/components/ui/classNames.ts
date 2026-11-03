import { cx } from '@/lib/cx';
import buttonStyles from './Button.module.css';
import formStyles from './Form.module.css';

export type ButtonVariant = 'default' | 'primary' | 'ghost' | 'danger' | 'dangerSolid';
export type ButtonSize = 'md' | 'sm' | 'xs';

export interface ButtonStyle {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Stretch to fill the row. */
  grow?: boolean;
}

/** Button classes, for elements that look like a button but aren't one (links, file labels). */
export const buttonClass = ({ variant = 'default', size = 'md', grow }: ButtonStyle = {}) =>
  cx(
    buttonStyles.btn,
    variant !== 'default' && buttonStyles[variant],
    size !== 'md' && buttonStyles[size],
    grow && buttonStyles.grow,
  );

/** Class for text inputs, textareas, and selects. `short` caps the width. */
export const inputClass = (short?: boolean) => cx(formStyles.input, short && formStyles.short);
