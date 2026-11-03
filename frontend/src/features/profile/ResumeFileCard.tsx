import type { ReactNode } from 'react';
import type { ResumeFile } from '@/api/types';
import { Icon } from '@/components/ui/Icon';
import { formatDay, plural } from '@/lib/format';
import { cx } from '@/lib/cx';
import styles from './ResumeFileCard.module.css';

/** The uploaded resume: name, size, when it was uploaded, and an action such as Replace. */
export function ResumeFileCard({
  file,
  action,
  bare,
}: {
  file: ResumeFile;
  action?: ReactNode;
  bare?: boolean;
}) {
  const details = [
    file.name.toLowerCase().endsWith('.pdf') ? 'PDF' : 'DOCX',
    file.pageCount ? plural(file.pageCount, 'page', 'pages') : null,
    `uploaded ${formatDay(file.uploadedAt)}`,
  ].filter(Boolean);

  return (
    <div className={cx(styles.card, bare && styles.bare)}>
      <span className={styles.icon}>
        <Icon name="file" size={22} stroke={1.6} />
      </span>
      <span className={styles.text}>
        <b>{file.name}</b>
        <span>{details.join(' · ')}</span>
      </span>
      {action}
    </div>
  );
}
