/** Settings panel for the confidence threshold below which the agent asks you. */
import type { AgentSettings } from '@/api/types';
import { Panel, PanelHead } from '@/components/ui/Panel';
import { cx } from '@/lib/cx';
import { useThresholdDraft } from './useThresholdDraft';
import styles from './ThresholdPanel.module.css';

const DEFAULT_THRESHOLD = 90;

interface ThresholdPanelProps {
  settings: AgentSettings;
}

/** A slider and number box that set the confidence threshold. */
export function ThresholdPanel({ settings }: ThresholdPanelProps) {
  const { value, text, error, setText, slideTo, commitSlider, commitText } = useThresholdDraft(
    settings.confidenceThreshold,
  );

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
          onChange={(event) => slideTo(event.target.value)}
          onPointerUp={commitSlider}
          onKeyUp={commitSlider}
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
          onChange={(event) => setText(event.target.value)}
          onBlur={commitText}
          onKeyDown={(event) => {
            if (event.key === 'Enter') commitText();
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
