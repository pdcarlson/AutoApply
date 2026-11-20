/** The "Watch it fill" drawer: a job's progress and every field filled so far. */
import { useEffect, useRef } from 'react';
import type { Job } from '@/api/types';
import { useAgentSettings, useJob, usePauseToggle } from '@/api/queries';
import { useOverlays } from '@/app/providers/overlays';
import { Chip } from '@/components/ui/Badges';
import { Drawer, DrawerSection } from '@/components/ui/Drawer';
import { FieldList } from '@/components/ui/FieldList';
import { Icon } from '@/components/ui/Icon';
import { Loading, LoadError } from '@/components/ui/LoadStates';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { LiveBrowser } from '@/components/liveBrowser/LiveBrowser';
import { jobChip, progressPercent, runStatusText } from '@/lib/jobStatus';
import { JobDrawerFooter } from './JobDrawerFooter';
import { JobStateNote } from './JobStateNote';
import styles from './JobDrawer.module.css';

/** What "Filled so far" says before any field is filled. */
function emptyFieldsText(job: Job) {
  if (job.state === 'queued') return 'Waiting for its turn in the queue.';
  if (job.state === 'waiting') return 'Waiting for tomorrow’s daily limit to reset.';
  return 'Nothing yet.';
}

interface JobDrawerProps {
  jobId: string;
}

/** "Watch it fill": a job's progress and every field the agent has filled so far. */
export function JobDrawer({ jobId }: JobDrawerProps) {
  const { close } = useOverlays();
  const job = useJob(jobId);
  const threshold = useAgentSettings().data?.confidenceThreshold;
  const { paused } = usePauseToggle();
  const bodyEnd = useRef<HTMLDivElement>(null);
  const data = job.data;

  // Follow along as fields are filled.
  useEffect(() => {
    if (data?.state === 'running') bodyEnd.current?.scrollIntoView({ block: 'end' });
  }, [data?.state, data?.progress.filled]);

  if (!data) {
    return (
      <Drawer
        labelledBy="drawer-title"
        onClose={close}
        head={
          <h2 id="drawer-title" className="sr-only">
            Job
          </h2>
        }
      >
        {job.isError ? <LoadError what="this job" onRetry={() => job.refetch()} /> : <Loading />}
      </Drawer>
    );
  }

  const chip = jobChip(data) ?? { tone: 'grey' as const, label: 'In Inbox' };
  const heldField =
    data.state === 'needs_input' && data.question
      ? { label: data.question.field, confidence: data.question.confidence }
      : null;
  const hasFields = data.fields.length || data.currentField || heldField;

  const head = (
    <>
      <div className={styles.top}>
        <Chip tone={chip.tone}>{chip.label}</Chip>
      </div>
      <h2 id="drawer-title" className={styles.title}>
        {data.role}
      </h2>
      <div className={styles.sub}>
        <span>
          {data.company} · {data.location}
        </span>
        <a href={data.url} target="_blank" rel="noopener noreferrer" className={styles.external}>
          Open posting
          <Icon name="external" size={14} />
        </a>
      </div>
    </>
  );

  const aside = data.liveView && (
    <LiveBrowser url={data.liveView.url} label={`${data.company} application form`} />
  );

  return (
    <Drawer
      labelledBy="drawer-title"
      onClose={close}
      head={head}
      footer={<JobDrawerFooter job={data} />}
      aside={aside}
    >
      <div className={styles.runStatus}>
        <div className={styles.runRow}>
          <b>{runStatusText(data, paused) || 'Not started'}</b>
          <span className="muted num">
            {data.progress.filled} of {data.progress.total} fields
          </span>
        </div>
        <ProgressBar value={progressPercent(data)} label="Form progress" />
        <span className="tiny muted">
          Runs in a fresh browser with no cookies from other runs.
          {threshold !== undefined &&
            ` Your threshold is ${threshold}: anything that scores lower comes to you as a question.`}
        </span>
      </div>
      <JobStateNote job={data} />
      <DrawerSection title="Filled so far">
        {hasFields ? (
          <FieldList fields={data.fields} pendingLabel={data.currentField} heldField={heldField} />
        ) : (
          <p className="small muted">{emptyFieldsText(data)}</p>
        )}
      </DrawerSection>
      <div ref={bodyEnd} />
    </Drawer>
  );
}
