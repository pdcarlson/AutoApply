import { useApplication } from '@/api/queries';
import { useOverlays } from '@/app/providers/overlays';
import { Loading, LoadError } from '@/components/ui/DataDisplay';
import { Modal, ModalHead } from '@/components/ui/Overlay';
import { formatDateTime } from '@/lib/format';
import styles from './applications.module.css';

/** Full-size view of the screenshot of the page after Submit (a dry run's: the filled form). */
export function ScreenshotModal({ applicationId }: { applicationId: string }) {
  const { close } = useOverlays();
  const app = useApplication(applicationId);
  const data = app.data;
  // A dry run never pressed Submit, so its screenshot is the filled form, not the page after.
  const dryRun = data?.submittedBy === 'agent' && !data.confirmation;

  return (
    <Modal labelledBy="screenshot-title" onClose={close} wide>
      <ModalHead onClose={close}>
        <h2 className="h3" id="screenshot-title">
          {data ? `${data.company} · submitted application` : 'Submitted application'}
        </h2>
      </ModalHead>
      {app.isError ? (
        <LoadError what="the screenshot" onRetry={() => app.refetch()} />
      ) : !data ? (
        <Loading />
      ) : data.screenshotUrl ? (
        <>
          <div className={styles.screenshotFrame}>
            <img
              className={styles.screenshot}
              src={data.screenshotUrl}
              alt={
                dryRun
                  ? `The filled ${data.company} application form`
                  : `The ${data.company} page after the application was submitted`
              }
            />
          </div>
          <p className="tiny muted">
            Saved {formatDateTime(data.submittedAt)},{' '}
            {dryRun
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
