import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router';
import { useAgentSettings, useJob, useMarkSubmitted } from '@/api/queries';
import { inboxJob } from '@/app/paths';
import { useOverlays } from '@/app/providers/overlays';
import { useToast } from '@/app/providers/toast';
import { Chip } from '@/components/ui/Badges';
import { Button } from '@/components/ui/Button';
import { Note } from '@/components/ui/Callouts';
import { FieldList, Loading, LoadError } from '@/components/ui/DataDisplay';
import { Icon } from '@/components/ui/Icon';
import { Drawer, DrawerSection } from '@/components/ui/Overlay';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { jobChip, progressPercent, runStatusText } from '@/lib/jobStatus';
import { usePauseToggle } from './usePauseToggle';
import styles from './JobDrawer.module.css';

/** "Watch it fill": a job's progress and every field the agent has filled so far. */
export function JobDrawer({ jobId }: { jobId: string }) {
  const { close, open } = useOverlays();
  const navigate = useNavigate();
  const notify = useToast();
  const job = useJob(jobId);
  const threshold = useAgentSettings().data?.confidenceThreshold;
  const { paused, pending, toggle } = usePauseToggle();
  const markSubmitted = useMarkSubmitted();
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
  const emptyText =
    data.state === 'queued'
      ? 'Waiting for its turn in the queue.'
      : data.state === 'waiting'
        ? 'Waiting for tomorrow’s daily limit to reset.'
        : 'Nothing yet.';

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

  const footer = (
    <>
      {data.state === 'ready' && (
        <Button variant="primary" grow onClick={() => open({ type: 'review', jobId: data.id })}>
          Review and submit
        </Button>
      )}
      {data.state === 'needs_input' && (
        <Button
          variant="primary"
          grow
          onClick={() => {
            close();
            navigate(inboxJob(data.id));
          }}
        >
          Answer in Inbox
        </Button>
      )}
      {data.state === 'handoff' && (
        <Button
          variant="primary"
          grow
          loading={markSubmitted.isPending}
          onClick={() =>
            markSubmitted.mutate(data.id, {
              onSuccess: () => {
                close();
                notify(`Marked as submitted. ${data.company} is in Applications.`);
              },
            })
          }
        >
          I submitted it
        </Button>
      )}
      <Button disabled={pending} onClick={toggle}>
        <Icon name={paused ? 'play' : 'pause'} size={15} />
        {paused ? 'Resume queue' : 'Pause queue'}
      </Button>
    </>
  );

  return (
    <Drawer labelledBy="drawer-title" onClose={close} head={head} footer={footer}>
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
      {data.state === 'ready' && (
        <Note tone="teal" title="Ready for your review">
          Every field is filled. The agent stopped before Submit and waits for you to approve it.
        </Note>
      )}
      {data.state === 'needs_input' && (
        <Note tone="amber" title="Waiting for you">
          The agent moved on to other jobs. Answer the question in your Inbox and this one picks up
          where it stopped.
        </Note>
      )}
      {data.state === 'handoff' && (
        <Note tone="amber" title="Stopped at a CAPTCHA">
          Finish it on {data.company}’s site. These are the answers to copy over.
        </Note>
      )}
      <DrawerSection title="Filled so far">
        {data.fields.length || data.currentField || heldField ? (
          <FieldList fields={data.fields} pendingLabel={data.currentField} heldField={heldField} />
        ) : (
          <p className="small muted">{emptyText}</p>
        )}
      </DrawerSection>
      <div ref={bodyEnd} />
    </Drawer>
  );
}
