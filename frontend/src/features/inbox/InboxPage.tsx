import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router';
import type { Job } from '@/api/types';
import {
  useAgentStatus,
  useApplyJobs,
  useCancelJobs,
  useJobs,
  useRestoreJob,
  useSession,
  useSkipJob,
} from '@/api/queries';
import { paths } from '@/app/paths';
import { useOverlays } from '@/app/providers/overlays';
import { useToast } from '@/app/providers/toast';
import { Button } from '@/components/ui/Button';
import { buttonClass } from '@/components/ui/classNames';
import { Banner } from '@/components/ui/Callouts';
import { FilterChips, Loading, LoadError, type FilterOption } from '@/components/ui/DataDisplay';
import { byNewest, INBOX_STATES, isInProgress, isWaitingOnUser } from '@/lib/jobStatus';
import { plural } from '@/lib/format';
import { ApplyingNow } from './ApplyingNow';
import { usePauseToggle } from './usePauseToggle';
import { JobRow } from './JobRow';
import { PasteLink } from './PasteLink';
import styles from './InboxPage.module.css';

type Filter = 'all' | 'matched' | 'added' | 'needs' | 'skip';

const FILTERS: FilterOption<Filter>[] = [
  { key: 'all', label: 'All' },
  { key: 'matched', label: 'New matches', dot: 'mark' },
  { key: 'added', label: 'You added', dot: 'ink' },
  { key: 'needs', label: 'Needs you', dot: 'amber' },
  { key: 'skip', label: 'Skip suggested', dot: 'red' },
];

const matches = (filter: Filter) => (job: Job) => {
  switch (filter) {
    case 'matched':
    case 'added':
      return job.source === filter;
    case 'needs':
      return job.state !== 'open';
    case 'skip':
      return job.state === 'open' && job.skipSuggested;
    default:
      return true;
  }
};

/** Jobs you add from a link start checked; matches and skip-suggested ones don't. */
const checkedByDefault = (job: Job) => job.source === 'added' && !job.skipSuggested;

const FLASH_MS = 2400;

export function InboxPage() {
  const jobs = useJobs();
  const session = useSession();
  const { paused, toggle: togglePause } = usePauseToggle();
  const dailyLimit = useAgentStatus().data?.dailyLimit;
  const apply = useApplyJobs();
  const cancel = useCancelJobs();
  const skip = useSkipJob();
  const restore = useRestoreJob();
  const notify = useToast();
  const navigate = useNavigate();
  const { open } = useOverlays();
  const [params, setParams] = useSearchParams();
  const [filter, setFilter] = useState<Filter>('all');
  const [checkedOverrides, setCheckedOverrides] = useState<Record<string, boolean>>({});
  const [flashId, setFlashId] = useState<string | null>(null);

  const expandedId = params.get('job');
  const all = (jobs.data ?? []).filter((job) => INBOX_STATES.includes(job.state)).sort(byNewest);
  const waiting = all.filter(isWaitingOnUser);
  const visible =
    filter === 'all' ? all : all.filter((j) => !isInProgress(j)).filter(matches(filter));
  const readyCount = (jobs.data ?? []).filter((job) => job.state === 'ready').length;

  const isChecked = (job: Job) =>
    job.state === 'open' && (checkedOverrides[job.id] ?? checkedByDefault(job));
  const selected = all.filter(isChecked).map((job) => job.id);

  const setExpanded = (jobId: string | null) =>
    setParams(jobId ? { job: jobId } : {}, { replace: true });

  // A deep link (?job=) shows that job: clear the filter and scroll it into view.
  useEffect(() => {
    if (!expandedId || !jobs.data) return;
    const smooth = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    document
      .getElementById(`job-${expandedId}`)
      ?.scrollIntoView({ block: 'center', behavior: smooth ? 'smooth' : 'auto' });
  }, [expandedId, jobs.data]);

  useEffect(() => {
    if (!flashId) return;
    const timer = setTimeout(() => setFlashId(null), FLASH_MS);
    return () => clearTimeout(timer);
  }, [flashId]);

  const showJob = (jobId: string) => {
    setFilter('all');
    setExpanded(jobId);
  };

  const applyTo = (ids: string[]) => {
    if (!ids.length) return;
    if (!session.data?.profileConfirmed) {
      open({ type: 'confirmProfile' });
      return;
    }
    apply.mutate(ids, {
      onSuccess: ({ queued, deferred }) => {
        setExpanded(null);
        const count = plural(ids.length, 'job', 'jobs');
        notify(
          deferred.length
            ? `Filling ${count}. ${queued.length} can go out today; ${deferred.length} wait until tomorrow${dailyLimit ? ` (daily limit ${dailyLimit})` : ''}.`
            : `Filling ${count}. You’ll review each one before it’s submitted.`,
          { undo: () => cancel.mutate(ids) },
        );
      },
      onError: (error) => notify(`Couldn’t start those applications. ${error.message}`),
    });
  };

  const skipJob = (job: Job) =>
    skip.mutate(job.id, {
      onSuccess: () => {
        if (expandedId === job.id) setExpanded(null);
        notify(`Skipped ${job.company}. It stays hidden, even after the next refresh.`, {
          undo: () => restore.mutate(job.id),
        });
      },
    });

  const onAdded = (job: Job) => {
    setFilter('all');
    setFlashId(job.id);
    notify(
      `Added ${job.company} · ${job.role} from ${job.ats}. It’s at the top of your Inbox, checked and ready.`,
    );
    requestAnimationFrame(() =>
      document.getElementById(`job-${job.id}`)?.scrollIntoView({ block: 'center' }),
    );
  };

  const counts = Object.fromEntries(
    FILTERS.map(({ key }) => [key, waiting.filter(matches(key)).length]),
  ) as Record<Filter, number>;

  return (
    <main id="main" className={styles.page}>
      <div className={styles.content}>
        <div className={styles.titleRow}>
          <h1 className="h1">Inbox</h1>
        </div>
        <PasteLink onAdded={onAdded} onShowJob={showJob} />

        {readyCount > 0 && (
          <Banner
            icon="check"
            title={`${plural(readyCount, 'application is', 'applications are')} ready to submit`}
            action={
              <Button
                size="sm"
                variant="primary"
                onClick={() => navigate(`${paths.applications}?filter=ready`)}
              >
                Review
              </Button>
            }
          >
            The agent filled {readyCount === 1 ? 'it' : 'them'} and stopped. Review and approve
            before anything is sent.
          </Banner>
        )}
        {paused && (
          <Banner
            tone="amber"
            icon="pause"
            action={
              <Button size="sm" onClick={togglePause}>
                Resume
              </Button>
            }
          >
            The queue is paused. Nothing new is submitted until you resume.
          </Banner>
        )}
        {session.data && !session.data.profileConfirmed && (
          <Banner
            tone="amber"
            icon="warn"
            title="Your profile isn’t confirmed yet."
            action={
              <Link className={buttonClass({ size: 'sm' })} to={paths.setupProfile}>
                Check my profile
              </Link>
            }
          >
            Applications only use your profile after you’ve checked it once.
          </Banner>
        )}

        <FilterChips
          label="Show"
          value={filter}
          onChange={setFilter}
          options={FILTERS.map((option) => ({ ...option, count: counts[option.key] }))}
        />

        <div className={styles.table}>
          <div className={`${styles.grid} ${styles.head}`} aria-hidden="true">
            <span />
            <span>Date</span>
            <span>Job</span>
            <span>Where</span>
            <span>Form</span>
            <span>Status</span>
            <span />
          </div>
          {jobs.isPending ? (
            <Loading label="Loading your Inbox…" />
          ) : jobs.isError ? (
            <LoadError what="your Inbox" onRetry={() => jobs.refetch()} />
          ) : visible.length ? (
            <ul>
              {visible.map((job) => (
                <JobRow
                  key={job.id}
                  job={job}
                  paused={paused}
                  expanded={expandedId === job.id}
                  checked={isChecked(job)}
                  flash={flashId === job.id}
                  onToggleExpanded={() => setExpanded(expandedId === job.id ? null : job.id)}
                  onToggleChecked={() =>
                    setCheckedOverrides((prev) => ({ ...prev, [job.id]: !isChecked(job) }))
                  }
                  onSkip={() => skipJob(job)}
                />
              ))}
            </ul>
          ) : (
            <p className={styles.empty}>
              {filter === 'all'
                ? 'Your Inbox is clear. Paste a job link to add one. New matches show up here each morning.'
                : 'Nothing in this filter.'}
            </p>
          )}
        </div>

        <div className={styles.phoneOnly}>
          <ApplyingNow variant="card" />
        </div>
      </div>

      <div className={styles.applyBar}>
        <span className={styles.applyHint}>
          Jobs you add from a link start checked. The agent fills each form, then you review it
          before it’s submitted.
        </span>
        <span className={styles.applyCount}>{selected.length} selected</span>
        <Button
          variant="primary"
          disabled={!selected.length}
          loading={apply.isPending}
          onClick={() => applyTo(selected)}
        >
          {selected.length ? `Apply to ${selected.length}` : 'Apply'}
        </Button>
      </div>
    </main>
  );
}
