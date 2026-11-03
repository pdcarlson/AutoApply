import { Link } from 'react-router';
import type { Job } from '@/api/types';
import { useAgentStatus, useJobs } from '@/api/queries';
import { paths } from '@/app/paths';
import { useOverlays } from '@/app/providers/overlays';
import { Button } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { isInProgress, progressPercent, runStatusText } from '@/lib/jobStatus';
import { cx } from '@/lib/cx';
import { usePauseToggle } from './usePauseToggle';
import styles from './ApplyingNow.module.css';

/** Jobs the agent is working through, in queue order. */
function useQueue(): Job[] {
  const { data: jobs = [] } = useJobs();
  const { data: status } = useAgentStatus();
  const active = jobs.filter(isInProgress);
  if (!status) return active;
  const byId = new Map(active.map((job) => [job.id, job]));
  const ordered = status.queue.flatMap((id) => byId.get(id) ?? []);
  // Anything the status hasn't caught up with yet goes last.
  return [...ordered, ...active.filter((job) => !status.queue.includes(job.id))];
}

/** What the agent is doing now, the pause control, and today's count against the daily limit. */
export function ApplyingNow({ variant }: { variant: 'sidebar' | 'card' }) {
  const queue = useQueue();
  const status = useAgentStatus().data;
  const { paused, pending, toggle } = usePauseToggle();
  const { open } = useOverlays();
  const sent = status?.sentToday ?? 0;
  const limit = status?.dailyLimit ?? 0;

  return (
    <section className={cx(styles.panel, styles[variant])} aria-label="Applying now">
      <div className={styles.head}>
        <h2 className="eyebrow">Applying now</h2>
        <Button size="xs" disabled={pending || !status} onClick={toggle}>
          <Icon name={paused ? 'play' : 'pause'} size={13} />
          {paused ? 'Resume' : 'Pause'}
        </Button>
      </div>
      {paused && (
        <p className={styles.pausedNote}>
          Paused. The form in progress finishes; nothing new starts.
        </p>
      )}
      {queue.length ? (
        queue.map((job) => (
          <button
            key={job.id}
            type="button"
            className={styles.item}
            aria-label={`Watch ${job.company} fill`}
            onClick={() => open({ type: 'job', jobId: job.id })}
          >
            <span className={styles.name}>
              <b>{job.company}</b>
              <span>{job.role}</span>
            </span>
            <ProgressBar value={progressPercent(job)} />
            <span className={styles.status}>{runStatusText(job, paused)}</span>
          </button>
        ))
      ) : (
        <p className="small muted">Nothing in progress. Check jobs and press Apply.</p>
      )}
      {status && (
        <div className={styles.limit}>
          <div className={styles.limitRow}>
            <span>Sent today</span>
            <b>
              {sent} of {limit}
            </b>
          </div>
          <ProgressBar thin value={limit ? (100 * sent) / limit : 0} />
        </div>
      )}
      <Link className={styles.link} to={paths.applications}>
        See all applications
      </Link>
    </section>
  );
}
