/** The modal showing an application's screenshot full size. */
import { useApplication } from '@/api/queries';
import { useApiImage } from '@/api/useApiImage';
import { useOverlays } from '@/app/providers/overlays';
import { Loading, LoadError } from '@/components/ui/LoadStates';
import { Modal, ModalHead } from '@/components/ui/Modal';
import { formatDateTime } from '@/lib/format';
import styles from './ScreenshotModal.module.css';

interface ScreenshotModalProps {
  applicationId: string;
}

/** Full-size view of the screenshot of the page after Submit (a dry run's: the filled form). */
export function ScreenshotModal({ applicationId }: ScreenshotModalProps) {
  const { close } = useOverlays();
  const application = useApplication(applicationId);
  const data = application.data;
  const screenshot = useApiImage(data?.screenshotUrl);
  // A dry run never pressed Submit, so its screenshot is the filled form, not the page after.
  const isDryRun = data?.submittedBy === 'agent' && !data.confirmation;

  return (
    <Modal labelledBy="screenshot-title" onClose={close} wide>
      <ModalHead onClose={close}>
        <h2 className="h3" id="screenshot-title">
          {data ? `${data.company} · submitted application` : 'Submitted application'}
        </h2>
      </ModalHead>
      {application.isError ? (
        <LoadError what="the screenshot" onRetry={() => application.refetch()} />
      ) : !data ? (
        <Loading />
      ) : data.screenshotUrl ? (
        <>
          <div className={styles.screenshotFrame}>
            <img
              className={styles.screenshot}
              src={screenshot}
              alt={
                isDryRun
                  ? `The filled ${data.company} application form`
                  : `The ${data.company} page after the application was submitted`
              }
            />
          </div>
          <p className="tiny muted">
            Saved {formatDateTime(data.submittedAt)},{' '}
            {isDryRun
              ? 'just before Submit (a dry run, so it wasn’t sent).'
              : 'after it was submitted.'}
          </p>
        </>
      ) : (
        <p className="small muted">
          There’s no screenshot for this one. You finished it on {data.company}’s site.
        </p>
      )}
    </Modal>
  );
}
