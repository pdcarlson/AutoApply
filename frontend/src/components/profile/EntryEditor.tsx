/** The open edit form for one profile entry. */
import { EXPERIENCE_KINDS, type Experience } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { Choice } from '@/components/ui/Choice';
import { Segmented } from '@/components/ui/Segmented';
import { EntryField } from './EntryField';
import type { EntryKind, EntryOf, EntrySpec } from './entrySpecs';
import styles from './EntryEditor.module.css';

interface EntryEditorProps<K extends EntryKind> {
  kind: K;
  entry: EntryOf<K>;
  spec: EntrySpec<EntryOf<K>>;
  saveLabel: string;
  saving?: boolean;
  onUpdate: (patch: Record<string, unknown>) => void;
  onSave: () => void;
  onRemove: () => void;
}

/** Edits an entry's fields; experience entries also get a type picker and a "current" box. */
export function EntryEditor<K extends EntryKind>({
  kind,
  entry,
  spec,
  saveLabel,
  saving,
  onUpdate,
  onSave,
  onRemove,
}: EntryEditorProps<K>) {
  const experience = kind === 'experience' ? (entry as Experience) : null;
  const kindLabelId = `${entry.id}-kind`;

  return (
    <div className={styles.entryEdit}>
      {experience && (
        <div className={styles.field}>
          <span className={styles.fieldLabel} id={kindLabelId}>
            Type
          </span>
          <Segmented
            labelledBy={kindLabelId}
            options={EXPERIENCE_KINDS}
            value={experience.kind}
            onChange={(value) => onUpdate({ kind: value })}
          />
          <span className="small muted">
            Only Work counts as a job. The agent uses the others for questions about leadership or
            involvement.
          </span>
        </div>
      )}
      <div className={styles.grid2}>
        {spec.fields.map((field) => (
          <EntryField
            key={field[0]}
            entry={entry as unknown as Record<string, unknown>}
            field={field}
            onChange={(value) => onUpdate({ [field[0]]: value })}
          />
        ))}
      </div>
      {experience && (
        <Choice
          type="checkbox"
          checked={experience.current}
          onChange={() => onUpdate({ current: !experience.current, end: '' })}
        >
          {experience.kind === 'work' ? 'I currently work here' : 'I’m still in this role'}
        </Choice>
      )}
      <div className={styles.actions}>
        <Button variant="primary" size="sm" loading={saving} onClick={onSave}>
          {saveLabel}
        </Button>
        <Button variant="danger" size="sm" onClick={onRemove}>
          Remove
        </Button>
      </div>
    </div>
  );
}
