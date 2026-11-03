import type { HTMLAttributes, ReactNode } from 'react';
import { cx } from '@/lib/cx';
import { Icon, type IconName } from './Icon';
import styles from './Callouts.module.css';

interface BannerProps {
  /** `amber` (dashed) means the user needs to act. */
  tone?: 'default' | 'amber';
  icon?: IconName;
  /** Leading element instead of an icon, e.g. a Dot. */
  leading?: ReactNode;
  title?: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
}

/** Full-width message across the top of a page, with an optional action on the right. */
export function Banner({ tone = 'default', icon, leading, title, children, action }: BannerProps) {
  return (
    <div className={cx(styles.banner, tone === 'amber' && styles.bannerAmber)}>
      {leading ?? (icon && <Icon name={icon} size={16} stroke={icon === 'check' ? 2.5 : 1.9} />)}
      <span className={styles.bannerText}>
        {title && <b>{title}</b>}
        {children && <span className={title ? 'small ink2' : undefined}>{children}</span>}
      </span>
      {action}
    </div>
  );
}

/** Boxed note inside a panel or drawer: a bold line and a sentence. */
export function Note({
  tone = 'grey',
  title,
  children,
}: {
  tone?: 'grey' | 'teal' | 'amber';
  title: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className={cx(styles.note, styles[`note-${tone}`])}>
      <b>{title}</b>
      {children && <span>{children}</span>}
    </div>
  );
}

/** Red error box with a warning icon. Announced to screen readers. */
export function ErrorBox({ children }: { children: ReactNode }) {
  return (
    <div className={styles.errorBox} role="alert">
      <Icon name="warn" />
      <span className={styles.errorText}>{children}</span>
    </div>
  );
}

export function Panel({ className, ...rest }: HTMLAttributes<HTMLElement>) {
  return <section className={cx(styles.panel, className)} {...rest} />;
}

export function PanelHead({ children }: { children: ReactNode }) {
  return <div className={styles.panelHead}>{children}</div>;
}
