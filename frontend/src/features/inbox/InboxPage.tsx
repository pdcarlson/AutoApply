/** The Inbox screen: jobs to apply to, and jobs waiting on the user. */
import { useState } from 'react';
import type { Job } from '@/api/types';
import { useJobs, usePauseToggle } from '@/api/queries';
import { useToast } from '@/app/providers/toast';
import { Loading, LoadError } from '@/components/ui/LoadStates';
import { ApplyingNow } from './ApplyingNow';
import { InboxBanners } from './InboxBanners';
import { inboxJobs, jobElementId, visibleJobs, type InboxFilter } from './inboxFilters';
import { InboxToolbar } from './InboxToolbar';
import { JobRow } from './JobRow';
import { JobTable } from './JobTable';
import { PasteLink } from './PasteLink';
import { useExpandedJob } from './useExpandedJob';
import { useFlashedJob } from './useFlashedJob';
import { useInboxActions } from './useInboxActions';
import { useJobChecks } from './useJobChecks';
import styles from './InboxPage.module.css';

/** Paste a link, filter and check jobs, and apply to one or many. */
export function InboxPage() {
  const jobs = useJobs();
  const notify = useToast();
  const { paused, toggle: togglePause } = usePauseToggle();
  const [filter, setFilter] = useState<InboxFilter>('all');
  const [flashId, setFlashId] = useFlashedJob();
  const { expandedId, setExpanded } = useExpandedJob(jobs.data);
  const { applyTo, skipJob, isApplying } = useInboxActions({ expandedId, setExpanded });

  const all = inboxJobs(jobs.data ?? []);
  const visible = visibleJobs(all, filter);
  const { isChecked, toggleChecked, checkedIds } = useJobChecks(all);

  const showJob = (jobId: string) => {
    setFilter('all');
    setExpanded(jobId);
  };

  const handleAdded = (job: Job) => {
    setFilter('all');
    setFlashId(job.id);
    notify(
      `Added ${job.company} · ${job.role} from ${job.ats}. It’s at the top of your Inbox, checked and ready.`,
    );
    requestAnimationFrame(() =>
      document.getElementById(jobElementId(job.id))?.scrollIntoView({ block: 'center' }),
    );
  };

  const emptyMessage =
    filter === 'all'
      ? 'Your Inbox is clear. Paste a job link to add one.'
      : 'Nothing in this filter.';
  const isEmpty = jobs.isSuccess && !visible.length;

  return (
    <main id="main" className={styles.page}>
      <div className={styles.content}>
        <div className={styles.titleRow}>
          <h1 className="h1">Inbox</h1>
        </div>
        <PasteLink onAdded={handleAdded} onShowJob={showJob} />
        <InboxBanners paused={paused} onResume={togglePause} />
        <InboxToolbar
          jobs={all}
          filter={filter}
          onFilterChange={setFilter}
          checkedCount={checkedIds.length}
          applying={isApplying}
          onApply={() => applyTo(checkedIds)}
        />
        <JobTable emptyMessage={isEmpty ? emptyMessage : undefined}>
          {jobs.isPending ? (
            <Loading label="Loading your Inbox…" />
          ) : jobs.isError ? (
            <LoadError what="your Inbox" onRetry={() => jobs.refetch()} />
          ) : (
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
                  onToggleChecked={() => toggleChecked(job)}
                  onSkip={() => skipJob(job)}
                  onApply={() => applyTo([job.id])}
                  applying={isApplying}
                />
              ))}
            </ul>
          )}
        </JobTable>
        <div className={styles.phoneOnly}>
          <ApplyingNow variant="card" />
        </div>
      </div>
    </main>
  );
}
