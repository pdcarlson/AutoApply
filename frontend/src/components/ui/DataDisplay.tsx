import type { ReactNode } from 'react';
import type { FilledField, ProfileCheck, TimelineEvent } from '@/api/types';
import { cx } from '@/lib/cx';
import { daysAgo, formatDateTime } from '@/lib/format';
import { Dot, type DotTone } from './Badges';
import { Icon } from './Icon';
import { Spinner } from './Spinner';
import styles from './DataDisplay.module.css';

export interface FilterOption<K extends string> {
  key: K;
  label: string;
  count?: number;
  dot?: DotTone | null;
}

/** Row of toggle chips that filter a list; exactly one is on. */
export function FilterChips<K extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: FilterOption<K>[];
  value: K;
  onChange: (key: K) => void;
  label: string;
}) {
  return (
    <div className={styles.filterChips} role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.key}
          type="button"
          className={cx(styles.filterChip, value === option.key && styles.on)}
          aria-pressed={value === option.key}
          onClick={() => onChange(option.key)}
        >
          {option.dot && <Dot tone={option.dot} />}
          {option.label}
          {option.count !== undefined && <span className={styles.countText}>{option.count}</span>}
        </button>
      ))}
    </div>
  );
}

const sourceTone = (field: FilledField) =>
  field.sourceKind === 'you'
    ? styles.sourceAmber
    : field.sourceKind === 'answer_bank'
      ? styles.sourceTeal
      : '';

interface FieldListProps {
  fields: FilledField[];
  /** A field the agent is filling right now, shown with a shimmer. */
  pendingLabel?: string | null;
  /** A field the agent paused on, waiting for the user. */
  heldField?: { label: string; confidence: number } | null;
  /** Wider source column (used in modals). */
  wide?: boolean;
}

/** Table of form fields: label, value, where the value came from, and its confidence score. */
export function FieldList({ fields, pendingLabel, heldField, wide }: FieldListProps) {
  return (
    <dl className={cx(styles.fieldList, wide && styles.fieldListWide)}>
      <div className={cx(styles.fieldRow, styles.fieldHead)} aria-hidden="true">
        <span>Field</span>
        <span>Value</span>
        <span className={styles.fieldSource}>Source</span>
        <span className={styles.fieldScore}>Score</span>
      </div>
      {fields.map((field, index) => (
        <div key={`${field.label}-${index}`} className={styles.fieldRow}>
          <dt>{field.label}</dt>
          <dd className={styles.fieldValue}>{field.value}</dd>
          <dd className={styles.fieldSource}>
            <span className={cx(styles.sourceTag, sourceTone(field))} title={field.source}>
              {field.source}
            </span>
          </dd>
          <dd className={styles.fieldScore} title="Confidence score">
            {field.confidence}
          </dd>
        </div>
      ))}
      {pendingLabel && (
        <div className={cx(styles.fieldRow, styles.pending)}>
          <dt>{pendingLabel}</dt>
          <dd className={styles.fieldValue} aria-label="Filling" />
          <dd className={styles.fieldSource} />
          <dd className={styles.fieldScore} />
        </div>
      )}
      {heldField && (
        <div className={cx(styles.fieldRow, styles.held)}>
          <dt>{heldField.label}</dt>
          <dd className={styles.fieldValue}>Waiting for your answer</dd>
          <dd className={styles.fieldSource}>
            <span className={cx(styles.sourceTag, styles.sourceAmber)}>Asked you</span>
          </dd>
          <dd className={cx(styles.fieldScore, styles.low)}>{heldField.confidence}</dd>
        </div>
      )}
    </dl>
  );
}

/** What happened to an application, oldest first. The `current` step shows elapsed time. */
export function Timeline({ events }: { events: TimelineEvent[] }) {
  return (
    <ol className={styles.timeline}>
      {events.map((event, index) => (
        <li key={index} className={cx(event.kind === 'current' && styles.current)}>
          <span className={cx(styles.timelineDot, styles[`dot-${event.kind}`])} />
          <span>{event.text}</span>
          <span className={styles.timelineWhen}>
            {event.kind === 'current'
              ? daysAgo(event.at).replace(' ago', '')
              : formatDateTime(event.at)}
          </span>
        </li>
      ))}
    </ol>
  );
}

const checkIcon = { ok: 'check', warn: 'warn', bad: 'bad' } as const;

/** How a posting compares with the profile: met, partly met, or not met. */
export function ChecksList({ checks, large }: { checks: ProfileCheck[]; large?: boolean }) {
  return (
    <ul className={cx(styles.checks, large && styles.checksLarge)}>
      {checks.map((check) => (
        <li key={check.text}>
          <Icon
            name={checkIcon[check.status]}
            size={large ? 20 : 18}
            stroke={check.status === 'ok' ? 2.5 : 2}
            className={styles[`check-${check.status}`]}
          />
          <span>{check.text}</span>
        </li>
      ))}
    </ul>
  );
}

export function Brand({ large }: { large?: boolean }) {
  return (
    <span className={cx(styles.brand, large && styles.brandLarge)}>
      <span className={styles.brandMark} aria-hidden="true">
        AA
      </span>
      <span>Auto Apply</span>
    </span>
  );
}

/** Centered muted message for an empty list. */
export function Empty({ children }: { children: ReactNode }) {
  return <p className={styles.empty}>{children}</p>;
}

/** Placeholder while a query loads. */
export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className={styles.loading} role="status">
      <Spinner />
      <span>{label}</span>
    </div>
  );
}

/** Shown in place of content whose query failed. */
export function LoadError({ onRetry, what = 'this' }: { onRetry?: () => void; what?: string }) {
  return (
    <div className={styles.loadError} role="alert">
      <span>We couldn’t load {what}. Check your connection and try again.</span>
      {onRetry && (
        <button type="button" className={styles.retry} onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}
