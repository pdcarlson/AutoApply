/** An editable list of short values shown as pills. */
import { useState, type KeyboardEvent } from 'react';
import { Icon } from './Icon';
import styles from './PillInput.module.css';

interface PillInputProps {
  items: string[];
  onChange: (items: string[]) => void;
  label: string;
  addLabel: string;
  placeholder?: string;
}

/** Editable list of short values shown as pills, e.g. skills or places. */
export function PillInput({ items, onChange, label, addLabel, placeholder }: PillInputProps) {
  // Null while the "+ Add" button shows; the text being typed once it is pressed.
  const [draft, setDraft] = useState<string | null>(null);

  const commit = () => {
    const value = (draft ?? '').trim();
    if (value && !items.includes(value)) onChange([...items, value]);
    setDraft(null);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      commit();
    } else if (event.key === 'Escape') {
      // Keeps Escape from also closing a surrounding dialog.
      event.stopPropagation();
      setDraft(null);
    }
  };

  return (
    <div className={styles.pills} role="group" aria-label={label}>
      {items.map((item) => (
        <span key={item} className={styles.pill}>
          {item}
          <button
            type="button"
            aria-label={`Remove ${item}`}
            onClick={() => onChange(items.filter((other) => other !== item))}
          >
            <Icon name="close" size={14} stroke={2} />
          </button>
        </span>
      ))}
      {draft === null ? (
        <button type="button" className={styles.pillAdd} onClick={() => setDraft('')}>
          + {addLabel}
        </button>
      ) : (
        <input
          className={styles.pillInput}
          aria-label={addLabel}
          placeholder={placeholder}
          value={draft}
          autoFocus
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={commit}
        />
      )}
    </div>
  );
}
