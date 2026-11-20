/** Where a saved answer has matched, been used, and came from. */
import type { Answer } from '@/api/types';
import { formatDay } from '@/lib/format';
import styles from './AnswerHistory.module.css';

/** "Title · 3", or just the title when there are none. */
const countedTitle = (title: string, count: number) => (count ? `${title} · ${count}` : title);

interface AnswerHistoryProps {
  answer: Answer;
}

/** Other wordings it matched, applications it was used on, and its source. */
export function AnswerHistory({ answer }: AnswerHistoryProps) {
  return (
    <>
      <div className={styles.group}>
        <span className="eyebrow">{countedTitle('Also matches', answer.alsoMatches.length)}</span>
        {answer.alsoMatches.length ? (
          answer.alsoMatches.map((match) => (
            <div key={match.wording} className={styles.match}>
              <span>“{match.wording}”</span>
              <span>{match.seenOn}</span>
            </div>
          ))
        ) : (
          <span className="small muted">No other wording seen yet.</span>
        )}
      </div>
      <div className={styles.group}>
        <span className="eyebrow">{countedTitle('Used on', answer.usedOn.length)}</span>
        {answer.usedOn.length ? (
          answer.usedOn.map((use, index) => (
            <div key={index} className={styles.usedRow}>
              <span>{use.company}</span>
              <span>
                {formatDay(use.at)}
                {use.note && ` · ${use.note}`}
              </span>
            </div>
          ))
        ) : (
          <span className="small muted">Not used yet.</span>
        )}
      </div>
      <div className={styles.group}>
        <span className="eyebrow">Where it came from</span>
        <span className="small ink2">{answer.source}</span>
      </div>
    </>
  );
}
