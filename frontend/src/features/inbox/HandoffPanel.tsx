import type { Job } from '@/api/types';
import { useMarkSubmitted, useSkipJob } from '@/api/queries';
import { useOverlays } from '@/app/providers/overlays';
import { useToast } from '@/app/providers/toast';
import { Button } from '@/components/ui/Button';
import { buttonClass } from '@/components/ui/classNames';
import { Icon } from '@/components/ui/Icon';
import styles from './panels.module.css';
import { VerificationCodeForm } from './VerificationCodeForm';

/** The agent stopped at a CAPTCHA (or a login/SSN field); the user finishes on the employer's site. */
export function HandoffPanel({ job }: { job: Job }) {
  const notify = useToast();
  const { open } = useOverlays();
  const markSubmitted = useMarkSubmitted();
  const skip = useSkipJob();

  if (job.asksForCode) {
    return (
      <div className={styles.ask}>
        <span className="eyebrow">Enter the code {job.ats} emailed you</span>
        <p className={styles.askQuestion}>
          {job.ats} sent a verification code to your email. Enter it here to finish this
          application.
        </p>
        <VerificationCodeForm
          job={job}
          onSubmitted={(app) =>
            notify(`Submitted to ${app.company}. Their confirmation page came back.`, {
              action: {
                label: 'See confirmation',
                run: () => open({ type: 'application', applicationId: app.id }),
              },
            })
          }
        />
        <div className={styles.row}>
          <Button size="sm" variant="ghost" onClick={() => open({ type: 'job', jobId: job.id })}>
            See its answers
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.ask}>
      <span className="eyebrow">Finish on {job.company}’s site</span>
      <p className={styles.askQuestion}>
        The form ends with a CAPTCHA. The agent never solves CAPTCHAs, so the last step is yours.
      </p>
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
