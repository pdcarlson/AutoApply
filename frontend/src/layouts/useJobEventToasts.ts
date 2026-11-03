import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router';
import type { JobState } from '@/api/types';
import { useJobs } from '@/api/queries';
import { inboxJob } from '@/app/paths';
import { useOverlays } from '@/app/providers/overlays';
import { useToast } from '@/app/providers/toast';

/**
 * Tells the user when the agent changes a job's state in the background (seen through polling):
 * it paused on a question, hit a CAPTCHA, finished filling a form, or ran into the daily limit.
 */
export function useJobEventToasts() {
  const { data: jobs } = useJobs();
  const notify = useToast();
  const navigate = useNavigate();
  const { open } = useOverlays();
  const previous = useRef<Map<string, JobState> | null>(null);

  useEffect(() => {
    if (!jobs) return;
    const before = previous.current;
    previous.current = new Map(jobs.map((job) => [job.id, job.state]));
    // The first load is the starting point, not news.
    if (!before) return;

    for (const job of jobs) {
      const was = before.get(job.id);
      if (!was || was === job.state) continue;

      if (job.state === 'needs_input') {
        notify(`${job.company} needs you: 1 question. The agent moved on to the next job.`, {
          action: { label: 'Answer it', run: () => navigate(inboxJob(job.id)) },
        });
      } else if (job.state === 'handoff') {
        notify(
          `${job.company}’s form has a CAPTCHA. It’s waiting in your Inbox for you to finish.`,
        );
      } else if (job.state === 'ready') {
        notify(
          `${job.company} is filled and waiting for your review. Nothing is sent until you approve it.`,
          { action: { label: 'Review it', run: () => open({ type: 'review', jobId: job.id }) } },
        );
      } else if (job.state === 'waiting' && was === 'queued') {
        notify('Daily limit reached. The rest wait until tomorrow.');
      }
    }
  }, [jobs, notify, navigate, open]);
}
