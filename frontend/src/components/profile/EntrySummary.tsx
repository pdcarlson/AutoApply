/** The read-only card for one profile entry, with an Edit button. */
import type { Education } from '@/api/types';
import { IconButton } from '@/components/ui/Button';
import { Dot } from '@/components/ui/Badges';
import { Icon } from '@/components/ui/Icon';
import { toBullets } from '@/lib/format';
import type { EntryKind, EntryOf } from './entrySpecs';
import styles from './EntrySummary.module.css';

interface EntrySummaryProps<K extends EntryKind> {
  kind: K;
  entry: EntryOf<K>;
  title: string;
  sub: string;
  onEdit: () => void;
}

/** Shows an entry's title, details and description bullets. */
export function EntrySummary<K extends EntryKind>({
  kind,
  entry,
  title,
  sub,
  onEdit,
}: EntrySummaryProps<K>) {
  const detail = 'detail' in entry ? entry.detail : '';
  const bullets = toBullets(detail);
  const coursework = kind === 'education' ? (entry as Education).coursework : '';
  const isMissingDescription = kind === 'projects' && !detail;

  return (
    <div className={styles.entry}>
      <div className={styles.entryText}>
        <b>{title}</b>
        {sub && <span>{sub}</span>}
        {coursework && <span className={styles.entryCourse}>Coursework: {coursework}</span>}
        {isMissingDescription ? (
          <span className={styles.thinHint}>
            <Dot tone="amber" />
            No description yet. Forms often ask what your part was and who used it.
          </span>
        ) : (
          bullets.length > 0 && (
            <ul className={styles.bullets}>
              {bullets.map((line, index) => (
                <li key={index}>{line}</li>
              ))}
            </ul>
          )
        )}
      </div>
      <IconButton label={`Edit ${title}`} onClick={onEdit}>
        <Icon name="pencil" size={16} stroke={1.75} />
      </IconButton>
    </div>
  );
}
