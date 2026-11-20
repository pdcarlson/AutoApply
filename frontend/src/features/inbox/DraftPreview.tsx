/** A drafted answer with the gap the user's reply has to fill. */
import styles from './DraftPreview.module.css';

interface DraftPreviewProps {
  draft: { text: string; gap: string };
  confidence: number;
  threshold: number | undefined;
}

/** Shows the draft text with its gap highlighted, and why it can't be sent yet. */
export function DraftPreview({ draft, confidence, threshold }: DraftPreviewProps) {
  const [before, after = ''] = draft.text.split(draft.gap);
  return (
    <div className={styles.draft}>
      <span className="eyebrow">Draft, from your profile only</span>
      <p>
        {before}
        <mark className={styles.gap}>{draft.gap}</mark>
        {after}
      </p>
      <span className="tiny muted">
        Confidence {confidence}
        {threshold !== undefined && `, below your threshold of ${threshold}`}. It has a gap, so it
        can’t be sent yet.
      </span>
    </div>
  );
}
