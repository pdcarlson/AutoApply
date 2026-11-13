import { useJob, useSubmitJob } from '@/api/queries';
import type { Application } from '@/api/types';
import { VerificationCodeForm } from '@/features/inbox/VerificationCodeForm';
import { useOverlays } from '@/app/providers/overlays';
import { useToast } from '@/app/providers/toast';
import { Button } from '@/components/ui/Button';
import { ErrorBox, Note } from '@/components/ui/Callouts';
import { FieldList, Loading, LoadError } from '@/components/ui/DataDisplay';
import { Modal, ModalHead } from '@/components/ui/Overlay';
import styles from './applications.module.css';

/** Last look at a filled form before the user approves submitting it. */
export function ReviewModal({ jobId }: { jobId: string }) {
  const { close, open } = useOverlays();
  const notify = useToast();
  const job = useJob(jobId);
  const submit = useSubmitJob();
  const data = job.data;

  const onSubmitted = (app: Application) => {
    close();
    notify(
      app.confirmation
        ? `Submitted to ${app.company}. Their confirmation page came back, so it’s confirmed.`
        : `Submitted to ${app.company}. It’s in Applications.`,
      {
        action: {
          label: 'See confirmation',
          run: () => open({ type: 'application', applicationId: app.id }),
        },
      },
    );
  };
  const onSubmit = () => submit.mutate(jobId, { onSuccess: onSubmitted });

  return (
    <Modal labelledBy="review-title" onClose={close} wide>
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
      {job.isError ? (
        <LoadError what="this application" onRetry={() => job.refetch()} />
      ) : !data ? (
        <Loading />
      ) : data.state === 'handoff' && data.asksForCode ? (
        <>
          <Note title={`${data.ats} emailed you a verification code`}>
            The agent pressed Submit, and {data.ats} wants a code it sent to your email before it
            takes the application. The form is still open and filled in.
          </Note>
          <VerificationCodeForm job={data} onSubmitted={onSubmitted} />
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
            answers below, then submit it.
          </Note>
          <FieldList fields={data.fields} wide />
          {submit.isError && <ErrorBox>That didn’t go through. {submit.error.message}</ErrorBox>}
          <div className={styles.reviewActions}>
            <Button
              variant="primary"
              loading={submit.isPending}
              loadingLabel="Submitting…"
              onClick={onSubmit}
            >
              Submit application
            </Button>
            <Button variant="ghost" disabled={submit.isPending} onClick={close}>
              Not yet
            </Button>
            <span className="tiny muted">It stays under Ready to submit until you approve it.</span>
          </div>
        </>
      )}
    </Modal>
  );
}
