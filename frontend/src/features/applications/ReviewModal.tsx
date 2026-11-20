/** The modal for a last look at a filled form before submitting it. */
import type { Application } from '@/api/types';
import { useJob, useSubmitJob } from '@/api/queries';
import { useOverlays } from '@/app/providers/overlays';
import { useToast } from '@/app/providers/toast';
import { Button } from '@/components/ui/Button';
import { ErrorBox, Note } from '@/components/ui/Callouts';
import { FieldList } from '@/components/ui/FieldList';
import { Loading, LoadError } from '@/components/ui/LoadStates';
import { Modal, ModalHead } from '@/components/ui/Modal';
import { VerificationCodeForm } from '@/components/jobs/VerificationCodeForm';
import { LiveBrowser } from '@/components/liveBrowser/LiveBrowser';
import styles from './ReviewModal.module.css';

interface ReviewModalProps {
  jobId: string;
}

/** Last look at a filled form before the user approves submitting it. */
export function ReviewModal({ jobId }: ReviewModalProps) {
  const { close, open } = useOverlays();
  const notify = useToast();
  const job = useJob(jobId);
  const submit = useSubmitJob();
  const data = job.data;

  const handleSubmitted = (application: Application) => {
    close();
    notify(
      application.confirmation
        ? `Submitted to ${application.company}. Their confirmation page came back, so it’s confirmed.`
        : `Submitted to ${application.company}. It’s in Applications.`,
      {
        action: {
          label: 'See confirmation',
          run: () => open({ type: 'application', applicationId: application.id }),
        },
      },
    );
  };
  const handleSubmit = () => submit.mutate(jobId, { onSuccess: handleSubmitted });

  const live = data?.liveView ?? null;

  const body = job.isError ? (
    <LoadError what="this application" onRetry={() => job.refetch()} />
  ) : !data ? (
    <Loading />
  ) : data.state === 'handoff' && data.asksForCode ? (
    <>
      <Note title={`${data.ats} emailed you a verification code`}>
        The agent pressed Submit, and {data.ats} wants a code it sent to your email before it takes
        the application. The form is still open and filled in.
      </Note>
      <VerificationCodeForm job={data} onSubmitted={handleSubmitted} />
      <div className={styles.reviewActions}>
        <Button variant="ghost" onClick={close}>
          Later
        </Button>
        <span className="tiny muted">It waits in your Inbox until you enter the code.</span>
      </div>
    </>
  ) : data.state !== 'ready' ? (
    <Note title="This one isn’t waiting for review">
      It may have been submitted already. Check Applications for its status.
    </Note>
  ) : (
    <>
      <Note title="Nothing has been sent yet">
        The agent filled all {data.fields.length} fields and stopped before Submit. Check the
        answers below{live ? ' and the form itself' : ''}, then submit it.
      </Note>
      <FieldList fields={data.fields} wide={!live} />
      {submit.isError && <ErrorBox>That didn’t go through. {submit.error.message}</ErrorBox>}
      <div className={styles.reviewActions}>
        <Button
          variant="primary"
          loading={submit.isPending}
          loadingLabel="Submitting…"
          onClick={handleSubmit}
        >
          Submit application
        </Button>
        <Button variant="ghost" disabled={submit.isPending} onClick={close}>
          Not yet
        </Button>
        <span className="tiny muted">It stays under Ready to submit until you approve it.</span>
      </div>
    </>
  );

  return (
    <Modal labelledBy="review-title" onClose={close} wide full={!!live}>
      <ModalHead onClose={close}>
        <div className={styles.headText}>
          <span className="eyebrow">Review before submitting</span>
          <h2 className="h3" id="review-title">
            {data ? `${data.company} · ${data.role}` : 'Application'}
          </h2>
          {data && (
            <span className="small muted">
              {data.location} · {data.ats} form
            </span>
          )}
        </div>
      </ModalHead>
      {live && data ? (
        <div className={styles.reviewSplit}>
          <div className={styles.reviewLive}>
            <LiveBrowser url={live.url} label={`${data.company} application form`} />
          </div>
          <div className={styles.reviewSide}>{body}</div>
        </div>
      ) : (
        body
      )}
    </Modal>
  );
}
