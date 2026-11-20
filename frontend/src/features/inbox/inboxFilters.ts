/** Which jobs the Inbox shows, filters and checks by default. */
import type { Job } from '@/api/types';
import type { FilterOption } from '@/components/ui/FilterChips';
import { byNewest, INBOX_STATES, isInProgress, isWaitingOnUser } from '@/lib/jobStatus';

/** The Inbox's filter chips. */
export type InboxFilter = 'all' | 'needs';

const FILTERS: FilterOption<InboxFilter>[] = [
  { key: 'all', label: 'All' },
  { key: 'needs', label: 'Needs you', dot: 'amber' },
];

const matchesFilter = (filter: InboxFilter) => (job: Job) =>
  filter === 'needs' ? job.state !== 'open' : true;

/** The DOM id of a job's row, used to scroll to it. */
export const jobElementId = (jobId: string) => `job-${jobId}`;

/** Jobs you add from a link start checked; matches and skip-suggested ones don't. */
export const isCheckedByDefault = (job: Job) => job.source === 'added' && !job.skipSuggested;

/** Every job that belongs in the Inbox, newest first. */
export const inboxJobs = (jobs: Job[]) =>
  jobs.filter((job) => INBOX_STATES.includes(job.state)).sort(byNewest);

/** The jobs a filter shows; "Needs you" leaves out jobs the agent is still working on. */
export const visibleJobs = (jobs: Job[], filter: InboxFilter) =>
  filter === 'all' ? jobs : jobs.filter((job) => !isInProgress(job)).filter(matchesFilter(filter));

/** The filter chips, each counting the jobs waiting on the user under it. */
export function filterOptions(jobs: Job[]) {
  const waiting = jobs.filter(isWaitingOnUser);
  return FILTERS.map((option) => ({
    ...option,
    count: waiting.filter(matchesFilter(option.key)).length,
  }));
}
