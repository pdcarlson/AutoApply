/** The scrolling content area of a signed-in screen, and its title row. */
import type { ReactNode } from 'react';
import { cx } from '@/lib/cx';
import styles from './Page.module.css';

interface PageProps {
  children: ReactNode;
  className?: string;
}

/** Scrolling content area for a signed-in screen. */
export function Page({ children, className }: PageProps) {
  return (
    <main id="main" className={cx(styles.page, className)}>
      {children}
    </main>
  );
}

interface PageTitleProps {
  title: string;
  /** Muted text beside the title, e.g. a count. */
  meta?: ReactNode;
  /** A lead paragraph under the title. */
  lede?: ReactNode;
  /** A control at the right of the title row. */
  action?: ReactNode;
}

/** Page title with optional muted meta text beside it, and an optional lead paragraph. */
export function PageTitle({ title, meta, lede, action }: PageTitleProps) {
  return (
    <div className={styles.head}>
      <div className={styles.headText}>
        <div className={styles.titleRow}>
          <h1 className="h1">{title}</h1>
          {meta && <span className="small muted num">{meta}</span>}
        </div>
        {lede && <p className="lede small">{lede}</p>}
      </div>
      {action}
    </div>
  );
}
