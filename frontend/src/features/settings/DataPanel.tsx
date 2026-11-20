/** Settings panel for downloading or deleting the user's data. */
import { useExportData } from '@/api/queries';
import { useOverlays } from '@/app/providers/overlays';
import { useToast } from '@/app/providers/toast';
import { Button } from '@/components/ui/Button';
import { Panel, PanelHead } from '@/components/ui/Panel';
import { Icon } from '@/components/ui/Icon';
import styles from './DataPanel.module.css';

/** Download-my-data and delete-my-account buttons. */
export function DataPanel() {
  const notify = useToast();
  const { open } = useOverlays();
  const exportData = useExportData(() =>
    notify('We couldn’t prepare your download. Try again in a moment.'),
  );

  return (
    <Panel aria-labelledby="data-title">
      <PanelHead>
        <h2 className="h3" id="data-title">
          Your data
        </h2>
      </PanelHead>
      <p className="small ink2">
        Download a copy of your profile, answers, and applications, or remove all of it from our
        servers.
      </p>
      <div className={styles.buttons}>
        <Button size="sm" loading={exportData.isPending} onClick={() => exportData.mutate()}>
          Download my data
        </Button>
        <Button size="sm" variant="danger" onClick={() => open({ type: 'deleteAccount' })}>
          <Icon name="trash" size={15} />
          Delete my account
        </Button>
      </div>
    </Panel>
  );
}
