/** The Inbox job that's open, kept in the URL as `?job=`. */
import { useEffect } from 'react';
import { useSearchParams } from 'react-router';
import type { Job } from '@/api/types';
import { jobElementId } from './inboxFilters';

/** Reads and sets `?job=`, and scrolls the open job into view whenever the job list loads. */
export function useExpandedJob(jobs: Job[] | undefined) {
  const [params, setParams] = useSearchParams();
  const expandedId = params.get('job');

  const setExpanded = (jobId: string | null) =>
    setParams(jobId ? { job: jobId } : {}, { replace: true });

  useEffect(() => {
    if (!expandedId || !jobs) return;
    const smooth = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    document
      .getElementById(jobElementId(expandedId))
      ?.scrollIntoView({ block: 'center', behavior: smooth ? 'smooth' : 'auto' });
  }, [expandedId, jobs]);

  return { expandedId, setExpanded };
}
