/** The Answer bank's table of saved answers. */
import type { ReactNode } from 'react';
import type { Answer } from '@/api/types';
import { MiniTag } from '@/components/ui/Badges';
import { formatDay } from '@/lib/format';
import { cx } from '@/lib/cx';
import styles from './AnswerTable.module.css';

interface AnswerTableProps {
  answers: Answer[];
  selectedId: string | undefined;
  onSelect: (id: string) => void;
  /** Shown instead of the rows: a loading, error or empty state. */
  placeholder?: ReactNode;
}

/** A header row over a scrolling list of answer rows. */
export function AnswerTable({ answers, selectedId, onSelect, placeholder }: AnswerTableProps) {
  return (
    <div className={styles.table}>
      <div className={cx(styles.grid, styles.tableHead)} aria-hidden="true">
        <span>Question</span>
        <span>Your answer</span>
        <span className={styles.right}>Used</span>
      </div>
      <div className={styles.tableBody}>
        {placeholder ??
          answers.map((answer) => (
            <AnswerRow
              key={answer.id}
              answer={answer}
              selected={answer.id === selectedId}
              onSelect={() => onSelect(answer.id)}
            />
          ))}
      </div>
    </div>
  );
}

interface AnswerRowProps {
  answer: Answer;
  selected: boolean;
  onSelect: () => void;
}

/** One answer: question with tags, the answer text, and how often it's been used. */
function AnswerRow({ answer, selected, onSelect }: AnswerRowProps) {
  const lastUsed = answer.lastUsedAt ? formatDay(answer.lastUsedAt) : 'Not used yet';
  return (
    <button
      type="button"
      className={cx(styles.grid, styles.row, selected && styles.on)}
      aria-pressed={selected}
      onClick={onSelect}
    >
      <span className={styles.question}>
        <b>{answer.question}</b>
        <span className={styles.meta}>
          <span>{answer.category}</span>
          {answer.company && <MiniTag>Only {answer.company}</MiniTag>}
          {answer.savedRecently && <MiniTag filled>Saved today</MiniTag>}
        </span>
      </span>
      <span className={styles.answer}>{answer.answer || '—'}</span>
      <span className={styles.used}>
        <b>{answer.timesUsed}×</b>
        <span>{lastUsed}</span>
      </span>
    </button>
  );
}
