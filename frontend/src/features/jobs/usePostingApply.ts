/** Applying to job board postings, with a toast summing up what started. */
import { useNavigate } from 'react-router';
import type { Posting } from '@/api/types';
import { useApplyToPostings as useApplyMutation, useSession } from '@/api/queries';
import { inboxJob, paths } from '@/app/paths';
import { useOverlays } from '@/app/providers/overlays';
import { useToast } from '@/app/providers/toast';
import { plural } from '@/lib/format';

/** `applyTo` starts applications (or asks to confirm the profile first); `onDone` runs after. */
export function usePostingApply(onDone: () => void) {
  const session = useSession();
  const apply = useApplyMutation();
  const notify = useToast();
  const navigate = useNavigate();
  const { open } = useOverlays();

  const applyTo = (postings: Posting[]) => {
    if (!postings.length) return;
    if (!session.data?.profileConfirmed) {
      open({ type: 'confirmProfile' });
      return;
    }
    apply.mutate(
      postings.map((posting) => posting.id),
      {
        onSuccess: ({ started, failed }) => {
          onDone();
          const waiting = started.filter((result) => result.deferred).length;
          const parts = [
            started.length &&
              `Filling ${plural(started.length, 'job', 'jobs')}. You’ll review each one before it’s submitted.`,
            waiting && `${waiting} wait until tomorrow because of your daily limit.`,
            failed.length &&
              `${plural(failed.length, 'posting', 'postings')} couldn’t be added. ${failed[0]}`,
          ];
          const [first] = started;
          notify(parts.filter(Boolean).join(' '), {
            action: first && {
              label: 'Show in Inbox',
              run: () => navigate(started.length === 1 ? inboxJob(first.job.id) : paths.inbox),
            },
          });
        },
      },
    );
  };

  return { applyTo, isApplying: apply.isPending };
}
