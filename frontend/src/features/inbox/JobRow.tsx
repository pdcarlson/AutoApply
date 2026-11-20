/** One job in the Inbox table, which expands to show its detail. */
import type { Job } from '@/api/types';
import { Chip } from '@/components/ui/Badges';
import { Button, IconButton } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { jobChip, jobDate, jobSummaryLine } from '@/lib/jobStatus';
import { formatDay } from '@/lib/format';
import { cx } from '@/lib/cx';
import { jobElementId } from './inboxFilters';
import { JobDetail } from './JobDetail';
import styles from './JobRow.module.css';

interface JobRowProps {
  job: Job;
  paused: boolean;
  expanded: boolean;
  checked: boolean;
  flash: boolean;
  onToggleExpanded: () => void;
  onToggleChecked: () => void;
  onSkip: () => void;
  onApply: () => void;
  /** True while an Apply request is in flight, which disables every row's Apply. */
  applying: boolean;
}

/** A selectable row with date, job, location, form and status; the title toggles the detail. */
export function JobRow({
  job,
  paused,
  expanded,
  checked,
  flash,
  onToggleExpanded,
  onToggleChecked,
  onSkip,
  onApply,
  applying,
}: JobRowProps) {
  const chip = jobChip(job);
  const date = jobDate(job);
  const sourceLabel = job.source === 'matched' ? 'New match' : 'You added';
  const dateTitle = job.source === 'added' ? 'Date you added it' : 'Date posted';

  return (
    <li
      id={jobElementId(job.id)}
      className={cx(styles.row, expanded && styles.open, flash && styles.flash)}
    >
      <div className={styles.grid}>
        <input
          type="checkbox"
          className={styles.check}
          aria-label={`Select ${job.company}`}
          checked={checked}
          disabled={job.state !== 'open'}
          onChange={onToggleChecked}
        />
        <span className={styles.when} title={dateTitle}>
          <b>{date.day}</b>
          <span>{date.label}</span>
        </span>
        <button
          type="button"
          className={styles.title}
          aria-expanded={expanded}
          onClick={onToggleExpanded}
        >
          <span className={styles.name}>
            <b>{job.company}</b> · {job.role}
          </span>
          <span className={styles.reason}>{jobSummaryLine(job, paused)}</span>
          <span className={styles.meta}>
            {job.location} · {job.ats} · {sourceLabel}
          </span>
        </button>
        <span className={styles.cell}>
          <span>{job.location}</span>
          {job.closesOn && <span className={styles.sub}>Closes {formatDay(job.closesOn)}</span>}
        </span>
        <span className={styles.cell}>
          <span>{job.ats}</span>
          <span className={styles.sub}>{sourceLabel}</span>
        </span>
        <span className={styles.status}>{chip && <Chip tone={chip.tone}>{chip.label}</Chip>}</span>
        <IconButton
          plain
          className={styles.expand}
          label={`Details for ${job.company}`}
          aria-expanded={expanded}
          onClick={onToggleExpanded}
        >
          <Icon name="chevron" className={cx(expanded && styles.flip)} />
        </IconButton>
        <span className={styles.rowApply}>
          {job.state === 'open' && (
            <Button
              size="sm"
              variant="primary"
              aria-label={`Apply to ${job.company}`}
              disabled={applying}
              onClick={onApply}
            >
              Apply
            </Button>
          )}
        </span>
      </div>
      {expanded && (
        <div className={styles.detail}>
          <JobDetail
            job={job}
            paused={paused}
            checked={checked}
            onCheck={onToggleChecked}
            onSkip={onSkip}
          />
        </div>
      )}
    </li>
  );
}
