/** Applying to and skipping Inbox jobs, with toasts that can undo them. */
import type { Job } from '@/api/types';
import {
  useAgentStatus,
  useApplyJobs,
  useCancelJobs,
  useRestoreJob,
  useSession,
  useSkipJob,
} from '@/api/queries';
import { useOverlays } from '@/app/providers/overlays';
import { useToast } from '@/app/providers/toast';
import { plural } from '@/lib/format';

interface InboxActionOptions {
  expandedId: string | null;
  setExpanded: (jobId: string | null) => void;
}

/** `applyTo` queues jobs (or asks to confirm the profile first); `skipJob` hides one. */
export function useInboxActions({ expandedId, setExpanded }: InboxActionOptions) {
  const session = useSession();
  const dailyLimit = useAgentStatus().data?.dailyLimit;
  const apply = useApplyJobs();
  const cancel = useCancelJobs();
  const skip = useSkipJob();
  const restore = useRestoreJob();
  const notify = useToast();
  const { open } = useOverlays();

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
        const limitNote = dailyLimit ? ` (daily limit ${dailyLimit})` : '';
        notify(
          deferred.length
            ? `Filling ${count}. ${queued.length} can go out today; ${deferred.length} wait until tomorrow${limitNote}.`
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

  return { applyTo, skipJob, isApplying: apply.isPending };
}
