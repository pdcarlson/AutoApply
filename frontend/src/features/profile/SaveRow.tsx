/** The "Save changes" button under a Profile section. */
import { Button } from '@/components/ui/Button';
import styles from './SaveRow.module.css';

interface SaveRowProps {
  isSaving: boolean;
  /** Why the section can't be saved yet, shown beside a disabled button. */
  blockedReason?: string | null;
  onSave: () => void;
}

/** A primary Save button, optionally disabled with a reason beside it. */
export function SaveRow({ isSaving, blockedReason = null, onSave }: SaveRowProps) {
  return (
    <div className={styles.saveRow}>
      <Button
        variant="primary"
        size="sm"
        loading={isSaving}
        disabled={!!blockedReason}
        onClick={onSave}
      >
        Save changes
      </Button>
      {blockedReason && <span className="small muted">{blockedReason}</span>}
    </div>
  );
}
