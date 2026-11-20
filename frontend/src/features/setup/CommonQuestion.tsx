/** One row of the setup questions, with a Skip toggle. */
import type { ReactNode } from 'react';
import type { CommonQuestionKey } from '@/api/types';
import { LinkButton } from '@/components/ui/Button';
import { cx } from '@/lib/cx';
import { questionLabelId } from './commonQuestionOptions';
import styles from './CommonQuestion.module.css';

/** Which questions are skipped, and how to skip or unskip one. */
export interface SkipState {
  skipped: CommonQuestionKey[];
  onToggleSkip: (key: CommonQuestionKey) => void;
}

interface CommonQuestionProps {
  questionKey: CommonQuestionKey;
  label: string;
  hint?: string;
  skips: SkipState;
  children: ReactNode;
}

/** A labelled question; the control is labelled by `q-<key>` and hidden while skipped. */
export function CommonQuestion({ questionKey, label, hint, skips, children }: CommonQuestionProps) {
  const isSkipped = skips.skipped.includes(questionKey);
  return (
    <div className={cx(styles.question, isSkipped && styles.skipped)}>
      <span className={styles.questionLabel} id={questionLabelId(questionKey)}>
        {label}
        {hint && <span className={styles.questionHint}>{hint}</span>}
      </span>
      <LinkButton small onClick={() => skips.onToggleSkip(questionKey)}>
        {isSkipped ? 'Undo skip' : 'Skip'}
      </LinkButton>
      <div className={styles.questionControl}>
        {isSkipped ? (
          <span className="small muted">Skipped. The agent will ask you if a form needs it.</span>
        ) : (
          children
        )}
      </div>
    </div>
  );
}
