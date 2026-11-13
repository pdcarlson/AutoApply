import type { Job } from '@/api/types';
import { useMarkSubmitted, useSkipJob } from '@/api/queries';
import { useOverlays } from '@/app/providers/overlays';
import { useToast } from '@/app/providers/toast';
import { Button } from '@/components/ui/Button';
import { buttonClass } from '@/components/ui/classNames';
import { Icon } from '@/components/ui/Icon';
import { formUrl } from '@/lib/jobLinks';
import styles from './panels.module.css';

export const DEFAULT_HANDOFF_REASON =
  'The form ends with a CAPTCHA. The agent never solves CAPTCHAs, so the last step is yours.';

/**
 * The agent stopped at a step only the user can do (a CAPTCHA, login or SSN field, or the site's
 * bot check turning it away); the user finishes on the employer's site. `job.reason` says which.
 */
export function HandoffPanel({ job }: { job: Job }) {
  const notify = useToast();
  const { open } = useOverlays();
  const markSubmitted = useMarkSubmitted();
  const skip = useSkipJob();

  return (
    <div className={styles.ask}>
      <span className="eyebrow">Finish on {job.company}’s site</span>
      <p className={styles.askQuestion}>{job.reason || DEFAULT_HANDOFF_REASON}</p>
      <p className="small ink2">
        Forms that ask for a Social Security number or a login come to you the same way. Every
        answer the agent would have entered is listed under its answers, so copying them over is
        quick.
      </p>
      <div className={styles.row}>
        <a
          className={buttonClass({ variant: 'primary', size: 'sm' })}
          href={formUrl(job)}
          target="_blank"
          rel="noopener noreferrer"
        >
          Open the form
          <Icon name="external" size={14} />
        </a>
        <Button size="sm" onClick={() => open({ type: 'job', jobId: job.id })}>
          See its answers
        </Button>
        <Button
          size="sm"
          loading={markSubmitted.isPending}
          onClick={() =>
            markSubmitted.mutate(job.id, {
              onSuccess: () => notify(`Marked as submitted. ${job.company} is in Applications.`),
            })
          }
        >
          I submitted it
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={skip.isPending}
          onClick={() =>
            skip.mutate(job.id, { onSuccess: () => notify(`Removed ${job.company}.`) })
          }
        >
          Remove
        </Button>
      </div>
    </div>
  );
}
