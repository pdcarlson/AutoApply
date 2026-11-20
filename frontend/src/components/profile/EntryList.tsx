/** Editable list of education, experience or project entries. */
import { useState } from 'react';
import { newId } from '@/lib/newId';
import { AddButton } from './AddButton';
import { EntryEditor } from './EntryEditor';
import { entrySpecFor, type EntryKind, type EntryOf } from './entrySpecs';
import { EntrySummary } from './EntrySummary';
import styles from './EntryList.module.css';

interface EntryListProps<K extends EntryKind> {
  kind: K;
  entries: EntryOf<K>[];
  onChange: (entries: EntryOf<K>[]) => void;
  /** Called with the final list after Save or Remove on one entry. */
  onCommit?: (entries: EntryOf<K>[]) => void;
  saving?: boolean;
}

/** List of entries with an Edit button each; one entry is edited at a time. */
export function EntryList<K extends EntryKind>({
  kind,
  entries,
  onChange,
  onCommit,
  saving,
}: EntryListProps<K>) {
  const spec = entrySpecFor(kind);
  const [editingId, setEditingId] = useState<string | null>(null);

  const updateEntry = (id: string, patch: Record<string, unknown>) =>
    onChange(entries.map((entry) => (entry.id === id ? { ...entry, ...patch } : entry)));

  const removeEntry = (id: string) => {
    const next = entries.filter((entry) => entry.id !== id);
    onChange(next);
    onCommit?.(next);
    setEditingId(null);
  };

  const saveEntry = () => {
    onCommit?.(entries);
    setEditingId(null);
  };

  const addEntry = () => {
    const id = newId(kind);
    onChange([...entries, { id, ...spec.blank() } as EntryOf<K>]);
    setEditingId(id);
  };

  return (
    <div className={styles.entryList}>
      {entries.map((entry) =>
        editingId === entry.id ? (
          <EntryEditor
            key={entry.id}
            kind={kind}
            entry={entry}
            spec={spec}
            saveLabel={onCommit ? 'Save' : 'Done'}
            saving={saving}
            onUpdate={(patch) => updateEntry(entry.id, patch)}
            onSave={saveEntry}
            onRemove={() => removeEntry(entry.id)}
          />
        ) : (
          <EntrySummary
            key={entry.id}
            kind={kind}
            entry={entry}
            title={spec.title(entry)}
            sub={spec.sub(entry)}
            onEdit={() => setEditingId(entry.id)}
          />
        ),
      )}
      {!entries.length && <p className="small muted">Nothing here yet.</p>}
      <AddButton onClick={addEntry}>{spec.add}</AddButton>
    </div>
  );
}
