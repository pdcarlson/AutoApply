/** A bordered content section and its heading row. */
import type { HTMLAttributes, ReactNode } from 'react';
import { cx } from '@/lib/cx';
import styles from './Panel.module.css';

/** A bordered `<section>` that groups related content on a page. */
export function Panel({ className, ...rest }: HTMLAttributes<HTMLElement>) {
  return <section className={cx(styles.panel, className)} {...rest} />;
}

interface PanelHeadProps {
  children: ReactNode;
}

/** The heading row at the top of a Panel, with room for an action on the right. */
export function PanelHead({ children }: PanelHeadProps) {
  return <div className={styles.panelHead}>{children}</div>;
}
