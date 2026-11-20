/** The message bubble under the paste-a-link box. */
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';
import { cx } from '@/lib/cx';
import type { PasteLinkMessage } from './pasteLinkMessages';
import styles from './PasteLinkPopover.module.css';

interface PasteLinkPopoverProps {
  message: PasteLinkMessage;
  onShowJob: (jobId: string) => void;
}

/** Shows progress, an error, or a note, with a jump to the job when it's already in the Inbox. */
export function PasteLinkPopover({ message, onShowJob }: PasteLinkPopoverProps) {
  if (message.kind === 'busy') {
    return (
      <div className={cx(styles.pop, styles.busy)} role="status">
        <Spinner />
        <span>{message.text}</span>
      </div>
    );
  }
  const { jobId } = message;
  return (
    <div
      className={cx(styles.pop, message.kind === 'error' && styles.error)}
      role={message.kind === 'error' ? 'alert' : 'status'}
    >
      <span className={styles.popTitle}>{message.title}</span>
      <span className="ink2">{message.text}</span>
      {message.hint && <span className="tiny muted">{message.hint}</span>}
      {jobId && (
        <div>
          <Button size="xs" onClick={() => onShowJob(jobId)}>
            Show it in my Inbox
          </Button>
        </div>
      )}
    </div>
  );
}
