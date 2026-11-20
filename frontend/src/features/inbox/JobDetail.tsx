/** The expanded part of an Inbox row: a question, a handoff, progress, or the checks. */
import type { Job } from '@/api/types';
import { useOverlays } from '@/app/providers/overlays';
import { Button } from '@/components/ui/Button';
import { ChecksList } from '@/components/ui/ChecksList';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { formSummaryText, isInProgress, progressPercent, runStatusText } from '@/lib/jobStatus';
import { cx } from '@/lib/cx';
import { HandoffPanel } from './HandoffPanel';
import { QuestionPanel } from './QuestionPanel';
import styles from './JobDetail.module.css';

interface JobDetailProps {
  job: Job;
  paused: boolean;
  checked: boolean;
  onCheck: () => void;
  onSkip: () => void;
}

/** Shows whatever the job needs next from the user, or how it compares to their profile. */
export function JobDetail({ job, paused, checked, onCheck, onSkip }: JobDetailProps) {
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
