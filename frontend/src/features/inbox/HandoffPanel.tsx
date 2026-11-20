/** What the user does when the agent hands a job back to them. */
import type { Application, Job } from '@/api/types';
import { useMarkSubmitted, useSkipJob } from '@/api/queries';
import { useOverlays } from '@/app/providers/overlays';
import { useToast } from '@/app/providers/toast';
import { Button } from '@/components/ui/Button';
import { buttonClass } from '@/components/ui/classNames';
import { Icon } from '@/components/ui/Icon';
import { VerificationCodeForm } from '@/components/jobs/VerificationCodeForm';
import styles from './HandoffPanel.module.css';

const DEFAULT_HANDOFF_REASON =
  'The form ends with a CAPTCHA. The agent never solves CAPTCHAs, so the last step is yours.';

interface HandoffPanelProps {
  job: Job;
}

/**
 * The agent stopped at a step only the user can do (a CAPTCHA, login, password or SSN field);
 * the user finishes on the employer's site. `job.reason` says which.
 */
export function HandoffPanel({ job }: HandoffPanelProps) {
  const notify = useToast();
  const { open } = useOverlays();
  const markSubmitted = useMarkSubmitted();
  const skip = useSkipJob();

  const showAnswers = () => open({ type: 'job', jobId: job.id });
  const handleCodeSubmitted = (application: Application) =>
    notify(`Submitted to ${application.company}. Their confirmation page came back.`, {
      action: {
        label: 'See confirmation',
        run: () => open({ type: 'application', applicationId: application.id }),
      },
    });
  const handleMarkSubmitted = () =>
    markSubmitted.mutate(job.id, {
      onSuccess: () => notify(`Marked as submitted. ${job.company} is in Applications.`),
    });
  const handleRemove = () =>
    skip.mutate(job.id, { onSuccess: () => notify(`Removed ${job.company}.`) });

  if (job.asksForCode) {
    return (
      <div className={styles.ask}>
        <span className="eyebrow">Enter the code {job.ats} emailed you</span>
        <p className={styles.askQuestion}>
          {job.ats} sent a verification code to your email. Enter it here to finish this
          application.
        </p>
        <VerificationCodeForm job={job} onSubmitted={handleCodeSubmitted} />
        <div className={styles.row}>
          <Button size="sm" variant="ghost" onClick={showAnswers}>
            See its answers
          </Button>
        </div>
      </div>
    );
  }

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
          href={job.url}
          target="_blank"
          rel="noopener noreferrer"
        >
          Open the form
          <Icon name="external" size={14} />
        </a>
        <Button size="sm" onClick={showAnswers}>
          See its answers
        </Button>
        <Button size="sm" loading={markSubmitted.isPending} onClick={handleMarkSubmitted}>
          I submitted it
        </Button>
        <Button size="sm" variant="ghost" disabled={skip.isPending} onClick={handleRemove}>
          Remove
        </Button>
      </div>
    </div>
  );
}
