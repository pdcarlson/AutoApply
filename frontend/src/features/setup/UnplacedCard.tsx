/** A piece of resume text the parser couldn't place, with ways to resolve it. */
import type { UnplacedSection } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import styles from './UnplacedCard.module.css';

/** What the user chose to do with an unplaced section. */
export type UnplacedAction = 'accept' | 'dismiss';

interface UnplacedCardProps {
  section: UnplacedSection;
  busy: boolean;
  onResolve: (action: UnplacedAction) => void;
}

/** Quotes the text and offers the parser's suggestion or "Leave it out". */
export function UnplacedCard({ section, busy, onResolve }: UnplacedCardProps) {
  return (
    <div className={styles.unplaced}>
      <span className={styles.unplacedTitle}>
        <Icon name="warn" size={16} />
        <b className="small">A section we couldn’t place</b>
      </span>
      <q>{section.text}</q>
      <div className={styles.row}>
        {section.suggestion && (
          <Button size="xs" disabled={busy} onClick={() => onResolve('accept')}>
            {section.suggestion}
          </Button>
        )}
        <Button size="xs" variant="ghost" disabled={busy} onClick={() => onResolve('dismiss')}>
          Leave it out
        </Button>
      </div>
      <span className="tiny muted">
        Every line of your resume ends up in a field or here, so nothing is lost.
      </span>
    </div>
  );
}
