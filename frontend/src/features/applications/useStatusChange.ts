/** Changing a sent application's status, with Undo. */
import type { Application, ApplicationStatus } from '@/api/types';
import { useSetApplicationStatus } from '@/api/queries';
import { useToast } from '@/app/providers/toast';
import { APPLICATION_STATUS_LABELS } from '@/lib/jobStatus';

/** Moves an application to a new status, with an Undo that moves it back. */
export function useStatusChange() {
  const notify = useToast();
  const setStatus = useSetApplicationStatus();

  return {
    pending: setStatus.isPending,
    change: (application: Application, status: ApplicationStatus) => {
      if (application.status === status) return;
      const previous = application.status;
      setStatus.mutate(
        { id: application.id, status },
        {
          onSuccess: () =>
            notify(`Moved ${application.company} to ${APPLICATION_STATUS_LABELS[status]}.`, {
              undo: () => setStatus.mutate({ id: application.id, status: previous }),
            }),
          onError: () => notify(`Couldn’t move ${application.company}. Try again.`),
        },
      );
    },
  };
}
