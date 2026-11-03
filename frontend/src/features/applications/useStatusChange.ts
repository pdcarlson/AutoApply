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
    change: (app: Application, status: ApplicationStatus) => {
      if (app.status === status) return;
      const previous = app.status;
      setStatus.mutate(
        { id: app.id, status },
        {
          onSuccess: () =>
            notify(`Moved ${app.company} to ${APPLICATION_STATUS_LABELS[status]}.`, {
              undo: () => setStatus.mutate({ id: app.id, status: previous }),
            }),
          onError: () => notify(`Couldn’t move ${app.company}. Try again.`),
        },
      );
    },
  };
}
