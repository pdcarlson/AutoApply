import type { JobDetail } from '@/api/types';
import { useJob, useSubmitJob, useSubmittedInBrowser } from '@/api/queries';
import { useOverlays } from '@/app/providers/overlays';
import { useToast } from '@/app/providers/toast';
import { Button } from '@/components/ui/Button';
import { ErrorBox, Note } from '@/components/ui/Callouts';
import { FieldList, Loading, LoadError } from '@/components/ui/DataDisplay';
import { Modal, ModalHead } from '@/components/ui/Overlay';
import { buttonClass } from '@/components/ui/classNames';
import { Icon } from '@/components/ui/Icon';
import { finishesInBrowser, formUrl } from '@/lib/jobLinks';
import styles from './applications.module.css';

/**
 * For sites that turn the agent's browser away (Lever): the user opens the form in their own
 * browser, where the AutoApply Filler extension fills it, and presses Submit there.
 */
function SubmitInBrowser({ job }: { job: JobDetail }) {
  const { close } = useOverlays();
  const notify = useToast();
  const done = useSubmittedInBrowser();
  return (
    <>
      <Note title={`You press Submit on ${job.ats}`}>
        {job.ats} doesn’t accept applications sent from the agent’s browser, so this last step
        happens in yours. With the AutoApply Filler extension, the form fills in by itself when it
        opens: check it and press Submit. AutoApply records it when the thank-you page shows.
      </Note>
      <FieldList fields={job.fields} wide />
      {done.isError && <ErrorBox>That didn’t go through. {done.error.message}</ErrorBox>}
      <div className={styles.reviewActions}>
        <a
          className={buttonClass({ variant: 'primary' })}
          href={formUrl(job)}
          target="_blank"
          rel="noopener noreferrer"
        >
          Open the form to submit
          <Icon name="external" size={14} />
        </a>
        <Button
          loading={done.isPending}
          onClick={() =>
            done.mutate(job.id, {
              onSuccess: () => {
                close();
                notify(`Marked as submitted. ${job.company} is in Applications.`);
              },
            })
          }
        >
          I submitted it
        </Button>
        <span className="tiny muted">No extension? The answers are listed above to copy over.</span>
      </div>
    </>
  );
}

/** Last look at a filled form before the user approves submitting it. */
export function ReviewModal({ jobId }: { jobId: string }) {
  const { close, open } = useOverlays();
  const notify = useToast();
  const job = useJob(jobId);
  const submit = useSubmitJob();
  const data = job.data;

  const onSubmit = () =>
    submit.mutate(jobId, {
      onSuccess: (app) => {
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
      },
    });

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
      ) : data.state !== 'ready' ? (
        <Note title="This one isn’t waiting for review">
          It may have been submitted already. Check Applications for its status.
        </Note>
      ) : finishesInBrowser(data) ? (
        <SubmitInBrowser job={data} />
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
