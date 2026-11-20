/** Settings panel that shows the queue and pauses or resumes it. */
import { useAgentStatus, usePauseToggle } from '@/api/queries';
import { Chip } from '@/components/ui/Badges';
import { Button } from '@/components/ui/Button';
import { Panel, PanelHead } from '@/components/ui/Panel';
import { Icon } from '@/components/ui/Icon';
import { plural } from '@/lib/format';

/** Running/paused state, the queue length, and a pause button. */
export function QueuePanel() {
  const status = useAgentStatus().data;
  const { paused, pending, toggle } = usePauseToggle();
  const queued = status?.queue.length ?? 0;
  const summary = paused
    ? 'Nothing new starts until you resume. '
    : 'The agent works through approved jobs one at a time. ';

  return (
    <Panel aria-labelledby="queue-title">
      <PanelHead>
        <h2 className="h3" id="queue-title">
          Queue
        </h2>
        {status && <Chip tone={paused ? 'amber' : 'teal'}>{paused ? 'Paused' : 'Running'}</Chip>}
      </PanelHead>
      <p className="small ink2">
        {summary}
        {plural(queued, 'job', 'jobs')} in the queue now.
      </p>
      <div>
        <Button
          size="sm"
          variant={paused ? 'primary' : 'default'}
          disabled={pending || !status}
          onClick={toggle}
        >
          <Icon name={paused ? 'play' : 'pause'} size={15} />
          {paused ? 'Resume the queue' : 'Pause the queue'}
        </Button>
      </div>
    </Panel>
  );
}
