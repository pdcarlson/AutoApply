/** An inline SVG icon from the app's icon set. */
import { cx } from '@/lib/cx';
import { ICON_PATHS } from './iconPaths';
import styles from './Icon.module.css';

/** The name of any icon in the set. */
export type IconName = keyof typeof ICON_PATHS;

interface IconProps {
  name: IconName;
  size?: number;
  stroke?: number;
  className?: string;
}

/** A line icon that takes the text color. Hidden from screen readers; label the control instead. */
export function Icon({ name, size = 18, stroke = 1.9, className }: IconProps) {
  return (
    <svg
      className={cx(styles.icon, className)}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={stroke}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {ICON_PATHS[name]}
    </svg>
  );
}
