import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import type { AgentSettings } from '@/api/types';
import { accountApi } from '@/api/endpoints';
import { useAgentSettings, useAgentStatus, useUpdateAgentSettings } from '@/api/queries';
import { useOverlays } from '@/app/providers/overlays';
import { useTheme, type ThemeChoice } from '@/app/providers/theme';
import { useToast } from '@/app/providers/toast';
import { Chip } from '@/components/ui/Badges';
import { Button } from '@/components/ui/Button';
import { Panel, PanelHead } from '@/components/ui/Callouts';
import { Loading, LoadError } from '@/components/ui/DataDisplay';
import { Segmented } from '@/components/ui/Form';
import { Icon } from '@/components/ui/Icon';
import { usePauseToggle } from '@/features/inbox/usePauseToggle';
import { Page, PageTitle } from '@/layouts/Page';
import { plural } from '@/lib/format';
import { cx } from '@/lib/cx';
import styles from './SettingsPage.module.css';

const DEFAULT_THRESHOLD = 90;
const MAX_DAILY_LIMIT = 50;

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

function ThresholdPanel({ settings }: { settings: AgentSettings }) {
  const notify = useToast();
  const update = useUpdateAgentSettings();
  const saved = settings.confidenceThreshold;
  const [value, setValue] = useState(saved);
  const [text, setText] = useState(String(saved));
  const [error, setError] = useState<string | null>(null);

  const commit = (next: number) => {
    if (next === saved) return;
    update.mutate(
      { confidenceThreshold: next },
      {
        onSuccess: () =>
          notify(`Threshold set to ${next}. It applies from the next field the agent fills.`),
      },
    );
  };

  const commitText = () => {
    const trimmed = text.trim();
    const n = Number(trimmed);
    if (!/^\d{1,3}$/.test(trimmed) || n > 100) {
      setError(`Enter a whole number from 0 to 100. Your threshold is still ${saved}.`);
      return;
    }
    setError(null);
    setValue(n);
    commit(n);
  };

  return (
    <Panel aria-labelledby="threshold-title">
      <PanelHead>
        <h2 className="h3" id="threshold-title">
          When to ask you
        </h2>
      </PanelHead>
      <p className="small ink2">
        The agent scores every value before it enters it. At or above your threshold, it fills the
        field. Below it, the job waits in your Inbox with a question.
      </p>
      <div className={styles.row}>
        <label className="sr-only" htmlFor="threshold-range">
          Confidence threshold
        </label>
        <input
          id="threshold-range"
          className={styles.range}
          type="range"
          min={0}
          max={100}
          value={value}
          onChange={(e) => {
            setValue(Number(e.target.value));
            setText(e.target.value);
            setError(null);
          }}
          onPointerUp={() => commit(value)}
          onKeyUp={() => commit(value)}
        />
        <label className="sr-only" htmlFor="threshold-number">
          Threshold, 0 to 100
        </label>
        <input
          id="threshold-number"
          className={cx(styles.numberBox, error && styles.invalid)}
          inputMode="numeric"
          value={text}
          aria-invalid={Boolean(error)}
          aria-describedby="threshold-help"
          onChange={(e) => setText(e.target.value)}
          onBlur={commitText}
          onKeyDown={(e) => {
            if (e.key === 'Enter') commitText();
          }}
        />
      </div>
      {error ? (
        <span className={styles.error} id="threshold-help" role="alert">
          {error}
        </span>
      ) : (
        <span className="tiny muted" id="threshold-help">
          Default is {DEFAULT_THRESHOLD}. Higher means more questions and fewer mistakes.
        </span>
      )}
    </Panel>
  );
}

function DailyLimitPanel({ settings }: { settings: AgentSettings }) {
  const notify = useToast();
  const update = useUpdateAgentSettings();
  const sentToday = useAgentStatus().data?.sentToday;
  const limit = settings.dailyLimit;

  const setLimit = (next: number) =>
    update.mutate(
      { dailyLimit: next },
      {
        onSuccess: () => notify(`Daily limit set to ${next}. It applies from the next submission.`),
      },
    );

  return (
    <Panel aria-labelledby="limit-title">
      <PanelHead>
        <h2 className="h3" id="limit-title">
          How many to send
        </h2>
      </PanelHead>
      <p className="small ink2">
        The most applications the agent submits in one day. Approved jobs past the limit wait until
        tomorrow.
      </p>
      <div className={styles.row}>
        <div className={styles.stepper} role="group" aria-label="Daily limit">
          <button
            type="button"
            aria-label="Lower the daily limit"
            disabled={limit <= 1 || update.isPending}
            onClick={() => setLimit(limit - 1)}
          >
            −
          </button>
          <output aria-live="polite">{limit}</output>
          <button
            type="button"
            aria-label="Raise the daily limit"
            disabled={limit >= MAX_DAILY_LIMIT || update.isPending}
            onClick={() => setLimit(limit + 1)}
          >
            +
          </button>
        </div>
        <span className="small ink2">
          per day{sentToday !== undefined && ` · ${sentToday} sent today`}
        </span>
      </div>
    </Panel>
  );
}

function QueuePanel() {
  const status = useAgentStatus().data;
  const { paused, pending, toggle } = usePauseToggle();
  const queued = status?.queue.length ?? 0;

  return (
    <Panel aria-labelledby="queue-title">
      <PanelHead>
        <h2 className="h3" id="queue-title">
          Queue
        </h2>
        {status && <Chip tone={paused ? 'amber' : 'teal'}>{paused ? 'Paused' : 'Running'}</Chip>}
      </PanelHead>
      <p className="small ink2">
        {paused
          ? 'Nothing new starts until you resume. '
          : 'The agent works through approved jobs one at a time. '}
        {plural(queued, 'job', 'jobs')} in the queue now.
      </p>
      <div>
        <Button
          size="sm"
          variant={paused ? 'primary' : 'default'}
          disabled={pending || !status}
          onClick={toggle}
        >
          <Icon name={paused ? 'play' : 'pause'} size={15} />
          {paused ? 'Resume the queue' : 'Pause the queue'}
        </Button>
      </div>
    </Panel>
  );
}

const THEMES: { value: ThemeChoice; label: string }[] = [
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
  { value: 'system', label: 'Match my device' },
];

function AppearancePanel() {
  const { choice, setChoice } = useTheme();
  return (
    <Panel aria-labelledby="appearance-title">
      <PanelHead>
        <h2 className="h3" id="appearance-title">
          Appearance
        </h2>
      </PanelHead>
      <Segmented
        labelledBy="appearance-title"
        options={THEMES}
        value={choice}
        onChange={setChoice}
      />
      <span className="tiny muted">
        Your choice is kept across screens and visits on this device.
      </span>
    </Panel>
  );
}

function DataPanel() {
  const notify = useToast();
  const { open } = useOverlays();
  const exportData = useMutation({
    mutationFn: accountApi.exportData,
    onError: () => notify('We couldn’t prepare your download. Try again in a moment.'),
  });

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
