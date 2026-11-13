import type { Job } from '@/api/types';
import { useOverlays } from '@/app/providers/overlays';
import { Chip } from '@/components/ui/Badges';
import { Button, IconButton } from '@/components/ui/Button';
import { ChecksList } from '@/components/ui/DataDisplay';
import { Icon } from '@/components/ui/Icon';
import { ProgressBar } from '@/components/ui/ProgressBar';
import {
  formSummaryText,
  isInProgress,
  jobChip,
  jobDate,
  jobSummaryLine,
  progressPercent,
  runStatusText,
} from '@/lib/jobStatus';
import { formatDay } from '@/lib/format';
import { cx } from '@/lib/cx';
import { HandoffPanel } from './HandoffPanel';
import { QuestionPanel } from './QuestionPanel';
import styles from './InboxPage.module.css';

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
  applying: boolean;
}

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

  return (
    <li
      id={`job-${job.id}`}
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
        <span
          className={styles.when}
          title={job.source === 'added' ? 'Date you added it' : 'Date posted'}
        >
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

function JobDetail({
  job,
  paused,
  checked,
  onCheck,
  onSkip,
}: {
  job: Job;
  paused: boolean;
  checked: boolean;
  onCheck: () => void;
  onSkip: () => void;
}) {
  const { open } = useOverlays();

  if (job.state === 'needs_input' && job.question) {
    return <QuestionPanel key={job.question.id} job={job} question={job.question} />;
  }
  if (job.state === 'handoff') return <HandoffPanel job={job} />;
  if (isInProgress(job)) {
    return (
      <div className={styles.progress}>
        <ProgressBar value={progressPercent(job)} className={styles.progressBar} />
        <span>{runStatusText(job, paused)}</span>
        <Button size="sm" onClick={() => open({ type: 'job', jobId: job.id })}>
          Watch it fill
        </Button>
      </div>
    );
  }

  const summary = formSummaryText(job);
  return (
    <>
      <span className={cx('eyebrow', job.skipSuggested && styles.redText)}>
        {job.skipSuggested ? 'Why we’d skip it' : 'Checked against your profile'}
      </span>
      <ChecksList checks={job.checks} />
      {summary && <p className="small ink2">{summary}</p>}
      <div className={styles.actions}>
        {job.skipSuggested && !checked && (
          <Button size="sm" onClick={onCheck}>
            Check it anyway
          </Button>
        )}
        <Button size="sm" variant="ghost" onClick={onSkip}>
          Skip this job
        </Button>
        <a className="small" href={job.url} target="_blank" rel="noopener noreferrer">
          Open posting
        </a>
      </div>
    </>
  );
}
