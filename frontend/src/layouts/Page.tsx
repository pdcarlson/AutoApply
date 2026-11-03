import type { ReactNode } from 'react';
import { cx } from '@/lib/cx';
import styles from './Page.module.css';

/** Scrolling content area for a signed-in screen. */
export function Page({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <main id="main" className={cx(styles.page, className)}>
      {children}
    </main>
  );
}

/** Page title with optional muted meta text beside it, and an optional lead paragraph. */
export function PageTitle({
  title,
  meta,
  lede,
  action,
}: {
  title: string;
  meta?: ReactNode;
  lede?: ReactNode;
  action?: ReactNode;
}) {
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
