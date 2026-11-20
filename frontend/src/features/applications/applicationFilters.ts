/** The Applications screen's status filter, kept in the URL as `?filter=`. */
import type { Application, ApplicationStatus, Job } from '@/api/types';
import type { FilterOption } from '@/components/ui/FilterChips';
import { APPLICATION_STATUSES, APPLICATION_STATUS_LABELS } from '@/lib/jobStatus';

/** Every row, jobs ready to submit, or one application status. */
export type ApplicationFilter = 'all' | 'ready' | ApplicationStatus;

const FILTER_LABELS: [ApplicationFilter, string][] = [
  ['all', 'All'],
  ['ready', 'Ready to submit'],
  ...APPLICATION_STATUSES.map(
    (status) => [status, APPLICATION_STATUS_LABELS[status]] as [ApplicationFilter, string],
  ),
];

/** The filter named in the URL, or `all` when it's missing or unknown. */
export function parseFilter(value: string | null): ApplicationFilter {
  const match = FILTER_LABELS.find(([key]) => key === value);
  return match ? match[0] : 'all';
}

/** The filter chips with their counts; "Ready to submit" gets a dot when anything is ready. */
export function filterOptions(
  readyJobs: Job[],
  applications: Application[],
): FilterOption<ApplicationFilter>[] {
  const countFor = (key: ApplicationFilter) =>
    key === 'all'
      ? readyJobs.length + applications.length
      : key === 'ready'
        ? readyJobs.length
        : applications.filter((application) => application.status === key).length;
  return FILTER_LABELS.map(([key, label]) => ({
    key,
    label,
    count: countFor(key),
    dot: key === 'ready' && readyJobs.length > 0 ? 'mark' : null,
  }));
}

/** The ready jobs and applications a filter shows. */
export function rowsFor(filter: ApplicationFilter, readyJobs: Job[], applications: Application[]) {
  return {
    readyJobs: filter === 'all' || filter === 'ready' ? readyJobs : [],
    applications:
      filter === 'all'
        ? applications
        : filter === 'ready'
          ? []
          : applications.filter((application) => application.status === filter),
  };
}
