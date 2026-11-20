/** A table of form fields with their values, sources, and confidence scores. */
import type { FilledField } from '@/api/types';
import { cx } from '@/lib/cx';
import styles from './FieldList.module.css';

/** Answers the user gave stand out in amber; Answer bank values in teal. */
function sourceTone(field: FilledField) {
  if (field.sourceKind === 'you') return styles.sourceAmber;
  if (field.sourceKind === 'answer_bank') return styles.sourceTeal;
  return '';
}

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
