/** Settings panel for how many applications the agent sends per day. */
import type { AgentSettings } from '@/api/types';
import { useAgentStatus, useUpdateAgentSettings } from '@/api/queries';
import { useToast } from '@/app/providers/toast';
import { Panel, PanelHead } from '@/components/ui/Panel';
import styles from './DailyLimitPanel.module.css';

const MIN_DAILY_LIMIT = 1;
const MAX_DAILY_LIMIT = 50;

interface DailyLimitPanelProps {
  settings: AgentSettings;
}

/** A − / + stepper that saves the daily limit on every press. */
export function DailyLimitPanel({ settings }: DailyLimitPanelProps) {
  const notify = useToast();
  const update = useUpdateAgentSettings();
  const sentToday = useAgentStatus().data?.sentToday;
  const limit = settings.dailyLimit;

  const setLimit = (next: number) =>
    update.mutate(
      { dailyLimit: next },
      {
        onSuccess: () => notify(`Daily limit set to ${next}. It applies from the next submission.`),
      },
    );

  return (
    <Panel aria-labelledby="limit-title">
      <PanelHead>
        <h2 className="h3" id="limit-title">
          How many to send
        </h2>
      </PanelHead>
      <p className="small ink2">
        The most applications the agent submits in one day. Approved jobs past the limit wait until
        tomorrow.
      </p>
      <div className={styles.row}>
        <div className={styles.stepper} role="group" aria-label="Daily limit">
          <button
            type="button"
            aria-label="Lower the daily limit"
            disabled={limit <= MIN_DAILY_LIMIT || update.isPending}
            onClick={() => setLimit(limit - 1)}
          >
            −
          </button>
          <output aria-live="polite">{limit}</output>
          <button
            type="button"
            aria-label="Raise the daily limit"
            disabled={limit >= MAX_DAILY_LIMIT || update.isPending}
            onClick={() => setLimit(limit + 1)}
          >
            +
          </button>
        </div>
        <span className="small ink2">
          per day{sentToday !== undefined && ` · ${sentToday} sent today`}
        </span>
      </div>
    </Panel>
  );
}
