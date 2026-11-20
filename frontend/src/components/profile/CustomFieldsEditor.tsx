/** Editor for free-form profile fields such as pronouns or citizenship. */
import type { CustomField } from '@/api/types';
import { IconButton } from '@/components/ui/Button';
import { inputClass } from '@/components/ui/classNames';
import { Icon } from '@/components/ui/Icon';
import { cx } from '@/lib/cx';
import { newId } from '@/lib/newId';
import { AddButton } from './AddButton';
import styles from './KeyValueList.module.css';

interface CustomFieldsEditorProps {
  fields: CustomField[];
  onChange: (fields: CustomField[]) => void;
}

/** Rows of field name and value that the agent fills when a form asks by that name. */
export function CustomFieldsEditor({ fields, onChange }: CustomFieldsEditorProps) {
  const updateField = (id: string, patch: Partial<CustomField>) =>
    onChange(fields.map((field) => (field.id === id ? { ...field, ...patch } : field)));
  const removeField = (id: string) => onChange(fields.filter((field) => field.id !== id));
  const addField = () => onChange([...fields, { id: newId('field'), label: '', value: '' }]);

  return (
    <div className={styles.list}>
      {fields.length ? (
        <div className={cx(styles.row, styles.head)} aria-hidden="true">
          <span>Field</span>
          <span>Value</span>
          <span />
        </div>
      ) : (
        <p className="small muted">
          Anything else forms ask for, like pronouns, a preferred name, or citizenship. The agent
          fills a field when a form asks for it by this name.
        </p>
      )}
      {fields.map((field) => (
        <div key={field.id} className={styles.row}>
          <input
            className={inputClass()}
            aria-label="Field name"
            placeholder="Field name, e.g. Pronouns"
            value={field.label}
            onChange={(event) => updateField(field.id, { label: event.target.value })}
          />
          <input
            className={inputClass()}
            aria-label={`Value for ${field.label || 'this field'}`}
            placeholder="Value, e.g. they/them"
            value={field.value}
            onChange={(event) => updateField(field.id, { value: event.target.value })}
          />
          <IconButton
            plain
            label={`Remove ${field.label || 'field'}`}
            onClick={() => removeField(field.id)}
          >
            <Icon name="close" size={16} />
          </IconButton>
        </div>
      ))}
      <AddButton onClick={addField}>Add a custom field</AddButton>
    </div>
  );
}
