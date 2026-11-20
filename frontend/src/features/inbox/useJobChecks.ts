/** Which Inbox jobs are checked for a bulk Apply. */
import { useState } from 'react';
import type { Job } from '@/api/types';
import { isCheckedByDefault } from './inboxFilters';

/** Tracks the user's check/uncheck choices on top of each job's default. */
export function useJobChecks(jobs: Job[]) {
  const [overrides, setOverrides] = useState<Record<string, boolean>>({});

  const isChecked = (job: Job) =>
    job.state === 'open' && (overrides[job.id] ?? isCheckedByDefault(job));

  const toggleChecked = (job: Job) =>
    setOverrides((previous) => ({ ...previous, [job.id]: !isChecked(job) }));

  const checkedIds = jobs.filter(isChecked).map((job) => job.id);

  return { isChecked, toggleChecked, checkedIds };
}
