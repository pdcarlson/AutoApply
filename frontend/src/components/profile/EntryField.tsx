/** One input in an entry's edit form: a text box, date picker or description box. */
import { DateInput } from '@/components/ui/DateInput';
import { TextAreaField } from '@/components/ui/TextAreaField';
import { TextField } from '@/components/ui/TextField';
import { inputClass } from '@/components/ui/classNames';
import { DESCRIPTION_HINT, type FieldSpec } from './entrySpecs';
import styles from './EntryField.module.css';

interface EntryFieldProps {
  entry: Record<string, unknown>;
  field: FieldSpec;
  onChange: (value: string) => void;
}

/** Renders the input that matches the field's type; an end date shows "Present" if current. */
export function EntryField({
  entry,
  field: [key, label, type, placeholder],
  onChange,
}: EntryFieldProps) {
  const value = String(entry[key] ?? '');
  if (type === 'textarea') {
    return (
      <TextAreaField
        className={styles.wide}
        label={label}
        rows={key === 'coursework' ? 2 : 4}
        value={value}
        placeholder={placeholder}
        hint={key === 'detail' ? DESCRIPTION_HINT : undefined}
        onChange={onChange}
      />
    );
  }
  if (type === 'date') {
    const isPresent = key === 'end' && entry.current === true;
    const id = `${String(entry.id)}-${key}`;
    return (
      <div className={styles.field}>
        <label htmlFor={id}>{label}</label>
        {isPresent ? (
          <input id={id} className={inputClass()} value="Present" disabled />
        ) : (
          <DateInput id={id} value={value} onChange={onChange} />
        )}
      </div>
    );
  }
  return <TextField label={label} value={value} placeholder={placeholder} onChange={onChange} />;
}
