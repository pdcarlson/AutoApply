/** The Inbox's table frame: a header row over the job rows or a state message. */
import type { ReactNode } from 'react';
import styles from './JobTable.module.css';

interface JobTableProps {
  /** Shown instead of the rows when no job matches. */
  emptyMessage?: string;
  /** The rows, or a loading or error state. */
  children?: ReactNode;
}

/** A bordered table with column headings; the headings hide on phones. */
export function JobTable({ emptyMessage, children }: JobTableProps) {
  return (
    <div className={styles.table}>
      <div className={styles.head} aria-hidden="true">
        <span />
        <span>Date</span>
        <span>Job</span>
        <span>Where</span>
        <span>Form</span>
        <span>Status</span>
        <span />
        <span />
      </div>
      {emptyMessage ? <p className={styles.empty}>{emptyMessage}</p> : children}
    </div>
  );
}
