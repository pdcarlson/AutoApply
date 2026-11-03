import { useAgentStatus, useSetPaused } from '@/api/queries';
import { useToast } from '@/app/providers/toast';

/** Pause/resume the agent's queue, with a toast saying what changed. */
export function usePauseToggle() {
  const notify = useToast();
  const status = useAgentStatus().data;
  const setPaused = useSetPaused();
  const paused = status?.paused ?? false;
  return {
    paused,
    pending: setPaused.isPending,
    toggle: () =>
      setPaused.mutate(!paused, {
        onSuccess: (next) =>
          notify(
            next.paused
              ? 'Paused. The form in progress finishes; nothing new starts.'
              : 'Resumed. The agent picks up the next job in the queue.',
          ),
      }),
  };
}
