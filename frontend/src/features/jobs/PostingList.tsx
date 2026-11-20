/** The job board's list of postings, with a column header row. */
import { Link } from 'react-router';
import type { Posting } from '@/api/types';
import { inboxJob } from '@/app/paths';
import { Chip } from '@/components/ui/Badges';
import { Button } from '@/components/ui/Button';
import { daysAgo } from '@/lib/format';
import { cx } from '@/lib/cx';
import styles from './PostingList.module.css';

interface PostingListProps {
  postings: Posting[];
  isChecked: (posting: Posting) => boolean;
  applying: boolean;
  onToggleChecked: (posting: Posting) => void;
  onApply: (posting: Posting) => void;
}

/** One row per posting: checkbox, fit score, job, why it fits, and actions. */
export function PostingList({
  postings,
  isChecked,
  applying,
  onToggleChecked,
  onApply,
}: PostingListProps) {
  return (
    <ul className={styles.list}>
      <li className={cx(styles.row, styles.listHead)} aria-hidden="true">
        <span />
        <span className={styles.fit}>Fit</span>
        <span className={styles.main}>Job</span>
        <span className={styles.why}>Why it fits</span>
        <span className={styles.actions} />
      </li>
      {postings.map((posting) => (
        <PostingRow
          key={posting.id}
          posting={posting}
          checked={isChecked(posting)}
          applying={applying}
          onToggleChecked={() => onToggleChecked(posting)}
          onApply={() => onApply(posting)}
        />
      ))}
    </ul>
  );
}

interface PostingRowProps {
  posting: Posting;
  checked: boolean;
  applying: boolean;
  onToggleChecked: () => void;
  onApply: () => void;
}

function PostingRow({ posting, checked, applying, onToggleChecked, onApply }: PostingRowProps) {
  const details = [
    posting.location,
    posting.ats,
    posting.postedAt && `Posted ${daysAgo(posting.postedAt)}`,
  ]
    .filter(Boolean)
    .join(' · ');
  const reasons = posting.fit.reasons.join(' · ') || 'Nothing on your profile matches it yet';

  return (
    <li className={styles.row}>
      <input
        type="checkbox"
        className={styles.check}
        aria-label={`Select ${posting.company}, ${posting.role}`}
        checked={checked}
        disabled={posting.status !== 'open'}
        onChange={onToggleChecked}
      />
      <span className={styles.fit} title="How well it fits your profile, out of 100">
        <b>{posting.fit.score}</b>
      </span>
      <div className={styles.main}>
        <b>
          {posting.company} · {posting.role}
        </b>
        <span className={styles.sub}>{details}</span>
      </div>
      <span className={styles.why}>{reasons}</span>
      <div className={styles.actions}>
        <a className="small" href={posting.url} target="_blank" rel="noopener noreferrer">
          Open posting
        </a>
        {posting.status === 'applied' ? (
          <Chip tone="grey">Applied</Chip>
        ) : posting.status === 'in_inbox' && posting.jobId ? (
          <Link className="small" to={inboxJob(posting.jobId)}>
            In your Inbox
          </Link>
        ) : (
          <Button
            size="sm"
            variant="primary"
            aria-label={`Apply to ${posting.company}, ${posting.role}`}
            disabled={applying}
            onClick={onApply}
          >
            Apply
          </Button>
        )}
      </div>
    </li>
  );
}
