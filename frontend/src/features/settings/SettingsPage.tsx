/** The Settings screen: threshold, daily limit, queue, appearance and data. */
import { useAgentSettings } from '@/api/queries';
import { Loading, LoadError } from '@/components/ui/LoadStates';
import { Page, PageTitle } from '@/layouts/Page';
import { cx } from '@/lib/cx';
import { AppearancePanel } from './AppearancePanel';
import { DailyLimitPanel } from './DailyLimitPanel';
import { DataPanel } from './DataPanel';
import { QueuePanel } from './QueuePanel';
import { ThresholdPanel } from './ThresholdPanel';
import styles from './SettingsPage.module.css';

/** Lays out the settings panels; the agent settings panels wait for their data. */
export function SettingsPage() {
  const settings = useAgentSettings();
  return (
    <Page>
      <div className={styles.narrow}>
        <PageTitle
          title="Settings"
          lede="When the agent asks you, how much it sends, and whether it’s running. Changes apply from the next field or submission."
        />
      </div>
      <div className={cx(styles.narrow, styles.body)}>
        {settings.isPending ? (
          <Loading />
        ) : settings.isError ? (
          <LoadError what="your settings" onRetry={() => settings.refetch()} />
        ) : (
          <>
            {/* Keyed on the saved value so the panel's draft resets when the server changes it. */}
            <ThresholdPanel key={settings.data.confidenceThreshold} settings={settings.data} />
            <DailyLimitPanel settings={settings.data} />
          </>
        )}
        <QueuePanel />
        <AppearancePanel />
        <DataPanel />
      </div>
    </Page>
  );
}
