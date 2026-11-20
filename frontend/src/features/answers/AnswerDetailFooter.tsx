/** Save, delete and cancel buttons under the answer detail. */
import { useState } from 'react';
import { Button } from '@/components/ui/Button';
import styles from './AnswerDetailFooter.module.css';

interface AnswerDetailFooterProps {
  isNew: boolean;
  canSave: boolean;
  isSaving: boolean;
  isDeleting: boolean;
  onSave: () => void;
  onDelete: () => void;
  onCancel: () => void;
}

/** Save plus Delete (with a confirm step) for a saved answer, or Save plus Cancel for a new one. */
export function AnswerDetailFooter({
  isNew,
  canSave,
  isSaving,
  isDeleting,
  onSave,
  onDelete,
  onCancel,
}: AnswerDetailFooterProps) {
  const [isConfirmingDelete, setIsConfirmingDelete] = useState(false);

  if (isConfirmingDelete && !isNew) {
    return (
      <div className={styles.detailFoot}>
        <div className={styles.confirmDelete}>
          <p className="small">
            <b>Delete this answer?</b> The agent will ask you again the next time a form needs it.
          </p>
          <div className={styles.buttons}>
            <Button size="sm" variant="dangerSolid" loading={isDeleting} onClick={onDelete}>
              Delete
            </Button>
            <Button size="sm" onClick={() => setIsConfirmingDelete(false)}>
              Keep it
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.detailFoot}>
      <Button
        variant="primary"
        size="sm"
        grow
        disabled={!canSave}
        loading={isSaving}
        onClick={onSave}
      >
        {isNew ? 'Save answer' : 'Save changes'}
      </Button>
      {isNew ? (
        <Button size="sm" onClick={onCancel}>
          Cancel
        </Button>
      ) : (
        <Button size="sm" variant="danger" onClick={() => setIsConfirmingDelete(true)}>
          Delete
        </Button>
      )}
    </div>
  );
}
