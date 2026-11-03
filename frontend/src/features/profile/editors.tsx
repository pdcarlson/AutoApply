/**
 * Controlled editors for the parts of a profile. Each takes the current value and reports
 * changes; the screen using it decides when to save (setup saves on Continue, the Profile page
 * saves per section).
 */
import { useState } from 'react';
import type {
  CustomField,
  Education,
  Experience,
  ProfileLink,
  ProfileUpdate,
  Project,
} from '@/api/types';
import { Button, IconButton } from '@/components/ui/Button';
import { Dot } from '@/components/ui/Badges';
import { Choice, DateInput, TextAreaField, TextField } from '@/components/ui/Form';
import { inputClass } from '@/components/ui/classNames';
import { Icon } from '@/components/ui/Icon';
import { formatSpan, toBullets } from '@/lib/format';
import { cx } from '@/lib/cx';
import styles from './editors.module.css';

const newId = (prefix: string) => `${prefix}-${crypto.randomUUID()}`;

// ===== Contact =====

type ContactKey =
  | 'name'
  | 'email'
  | 'phone'
  | 'street'
  | 'street2'
  | 'city'
  | 'state'
  | 'zip'
  | 'country';
export type Contact = Pick<ProfileUpdate, ContactKey>;

const ADDRESS: [ContactKey, string, string, string][] = [
  ['street', 'Street address', 'e.g. 412 Main Street', styles.street],
  ['street2', 'Apt, suite, unit (optional)', 'e.g. Apt 3B', styles.street2],
  ['city', 'City', 'City', styles.city],
  ['state', 'State', 'e.g. NY', styles.state],
  ['zip', 'ZIP code', 'e.g. 12180', styles.zip],
  ['country', 'Country', 'Country', styles.country],
];

export function ContactFields({
  value,
  onChange,
}: {
  value: Contact;
  onChange: (patch: Partial<Contact>) => void;
}) {
  return (
    <div className={styles.contact}>
      <div className={styles.grid2}>
        <TextField
          label="Full name"
          placeholder="Your name"
          autoComplete="name"
          value={value.name}
          onChange={(name) => onChange({ name })}
        />
        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          value={value.email}
          onChange={(email) => onChange({ email })}
        />
        <TextField
          label="Phone"
          type="tel"
          autoComplete="tel"
          placeholder="(555) 555-5555"
          value={value.phone}
          onChange={(phone) => onChange({ phone })}
        />
      </div>
      <span className="eyebrow">Address</span>
      <div className={styles.address}>
        {ADDRESS.map(([key, label, placeholder, className]) => (
          <TextField
            key={key}
            className={className}
            label={label}
            placeholder={placeholder}
            value={value[key]}
            onChange={(v) => onChange({ [key]: v })}
          />
        ))}
      </div>
    </div>
  );
}

// ===== Links =====

const FIXED_LINK_PLACEHOLDERS: Record<string, string> = {
  Website: 'https://yourname.dev',
  'Website / portfolio': 'https://yourname.dev',
  LinkedIn: 'https://linkedin.com/in/…',
  GitHub: 'https://github.com/…',
};

export function LinksEditor({
  links,
  onChange,
}: {
  links: ProfileLink[];
  onChange: (links: ProfileLink[]) => void;
}) {
  const update = (id: string, patch: Partial<ProfileLink>) =>
    onChange(links.map((link) => (link.id === id ? { ...link, ...patch } : link)));

  return (
    <div className={styles.kvList}>
      {links.map((link) => (
        <div key={link.id} className={styles.kvRow}>
          {link.fixed ? (
            <label className={styles.kvLabel} htmlFor={`link-${link.id}`}>
              {link.label}
            </label>
          ) : (
            <input
              className={inputClass()}
              aria-label="Link name"
              placeholder="Name, e.g. Blog"
              value={link.label}
              onChange={(e) => update(link.id, { label: e.target.value })}
            />
          )}
          <input
            id={`link-${link.id}`}
            className={inputClass()}
            type="url"
            inputMode="url"
            placeholder={FIXED_LINK_PLACEHOLDERS[link.label] ?? 'https://'}
            value={link.url}
            onChange={(e) => update(link.id, { url: e.target.value })}
          />
          {link.fixed ? (
            <span />
          ) : (
            <IconButton
              plain
              label={`Remove ${link.label || 'link'}`}
              onClick={() => onChange(links.filter((l) => l.id !== link.id))}
            >
              <Icon name="close" size={16} />
            </IconButton>
          )}
        </div>
      ))}
      <AddButton
        onClick={() =>
          onChange([...links, { id: newId('link'), label: '', url: '', fixed: false }])
        }
      >
        Add another link
      </AddButton>
    </div>
  );
}

// ===== Custom fields =====

export function CustomFieldsEditor({
  fields,
  onChange,
}: {
  fields: CustomField[];
  onChange: (fields: CustomField[]) => void;
}) {
  const update = (id: string, patch: Partial<CustomField>) =>
    onChange(fields.map((field) => (field.id === id ? { ...field, ...patch } : field)));

  return (
    <div className={styles.kvList}>
      {fields.length ? (
        <div className={cx(styles.kvRow, styles.kvHead)} aria-hidden="true">
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
        <div key={field.id} className={styles.kvRow}>
          <input
            className={inputClass()}
            aria-label="Field name"
            placeholder="Field name, e.g. Pronouns"
            value={field.label}
            onChange={(e) => update(field.id, { label: e.target.value })}
          />
          <input
            className={inputClass()}
            aria-label={`Value for ${field.label || 'this field'}`}
            placeholder="Value, e.g. they/them"
            value={field.value}
            onChange={(e) => update(field.id, { value: e.target.value })}
          />
          <IconButton
            plain
            label={`Remove ${field.label || 'field'}`}
            onClick={() => onChange(fields.filter((f) => f.id !== field.id))}
          >
            <Icon name="close" size={16} />
          </IconButton>
        </div>
      ))}
      <AddButton
        onClick={() => onChange([...fields, { id: newId('field'), label: '', value: '' }])}
      >
        Add a custom field
      </AddButton>
    </div>
  );
}

// ===== Education / experience / projects =====

type EntryKind = 'education' | 'experience' | 'projects';
type EntryOf<K extends EntryKind> = K extends 'education'
  ? Education
  : K extends 'experience'
    ? Experience
    : Project;

type FieldSpec = [
  key: string,
  label: string,
  type: 'text' | 'date' | 'textarea',
  placeholder?: string,
];

const DESCRIPTION_HINT =
  'Each line becomes a bullet. The agent writes answers only from what’s here.';

interface EntrySpec<E> {
  add: string;
  title: (entry: E) => string;
  sub: (entry: E) => string;
  blank: () => Omit<E, 'id'>;
  fields: FieldSpec[];
}

const ENTRY_SPECS: { [K in EntryKind]: EntrySpec<EntryOf<K>> } = {
  experience: {
    add: 'Add experience',
    title: (e) => [e.title, e.org].filter(Boolean).join(' · ') || 'New experience',
    sub: (e) => [formatSpan(e.start, e.end, e.current), e.location].filter(Boolean).join(' · '),
    blank: () => ({
      title: '',
      org: '',
      location: '',
      start: '',
      end: '',
      current: false,
      detail: '',
    }),
    fields: [
      ['title', 'Title', 'text', 'e.g. Software Intern'],
      ['org', 'Employer', 'text', 'Company name'],
      ['location', 'Location', 'text', 'City, State or Remote'],
      ['start', 'Start date', 'date'],
      ['end', 'End date', 'date'],
      [
        'detail',
        'Description',
        'textarea',
        'One bullet per line, e.g.\nBuilt the Python service that tracked robot telemetry',
      ],
    ],
  },
  education: {
    add: 'Add education',
    title: (e) => e.school || 'New education',
    sub: (e) =>
      [
        [e.degreeType, e.major].filter(Boolean).join(', '),
        e.gpa && `GPA ${e.gpa}`,
        e.location,
        formatSpan(e.start, e.end),
      ]
        .filter(Boolean)
        .join(' · '),
    blank: () => ({
      school: '',
      degreeType: '',
      major: '',
      gpa: '',
      location: '',
      start: '',
      end: '',
      coursework: '',
    }),
    fields: [
      ['school', 'School', 'text', 'School name'],
      ['location', 'Location', 'text', 'City, State'],
      ['degreeType', 'Degree type', 'text', 'e.g. Bachelor of Science (B.S.)'],
      ['major', 'Major', 'text', 'e.g. Computer Science'],
      ['gpa', 'GPA', 'text', 'e.g. 3.4'],
      ['start', 'Start date', 'date'],
      ['end', 'End date (or expected)', 'date'],
      ['coursework', 'Relevant coursework', 'textarea', 'e.g. Data Structures, Operating Systems'],
    ],
  },
  projects: {
    add: 'Add project',
    title: (p) => p.name || 'New project',
    sub: (p) => p.tech,
    blank: () => ({ name: '', tech: '', detail: '' }),
    fields: [
      ['name', 'Project', 'text', 'Project name'],
      ['tech', 'Tools', 'text', 'e.g. React, Firebase'],
      [
        'detail',
        'Description',
        'textarea',
        'One bullet per line, e.g.\nBuilt the frontend with one other student',
      ],
    ],
  },
};

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
  // TypeScript can't narrow a mapped type through a generic key, so name the result's type.
  const spec = ENTRY_SPECS[kind] as EntrySpec<EntryOf<K>>;
  const [editing, setEditing] = useState<string | null>(null);

  const update = (id: string, patch: Record<string, unknown>) =>
    onChange(entries.map((entry) => (entry.id === id ? { ...entry, ...patch } : entry)));

  const remove = (id: string) => {
    const next = entries.filter((entry) => entry.id !== id);
    onChange(next);
    onCommit?.(next);
    setEditing(null);
  };

  const add = () => {
    const id = newId(kind);
    onChange([...entries, { id, ...spec.blank() } as EntryOf<K>]);
    setEditing(id);
  };

  return (
    <div className={styles.entryList}>
      {entries.map((entry) =>
        editing === entry.id ? (
          <div key={entry.id} className={styles.entryEdit}>
            <div className={styles.grid2}>
              {spec.fields.map(([key, label, type, placeholder]) => (
                <EntryField
                  key={key}
                  entry={entry as unknown as Record<string, unknown>}
                  field={[key, label, type, placeholder]}
                  onChange={(value) => update(entry.id, { [key]: value })}
                />
              ))}
            </div>
            {kind === 'experience' && (
              <Choice
                type="checkbox"
                checked={(entry as Experience).current}
                onChange={() =>
                  update(entry.id, { current: !(entry as Experience).current, end: '' })
                }
              >
                I currently work here
              </Choice>
            )}
            <div className={styles.actions}>
              <Button
                variant="primary"
                size="sm"
                loading={saving}
                onClick={() => {
                  onCommit?.(entries);
                  setEditing(null);
                }}
              >
                {onCommit ? 'Save' : 'Done'}
              </Button>
              <Button variant="danger" size="sm" onClick={() => remove(entry.id)}>
                Remove
              </Button>
            </div>
          </div>
        ) : (
          <EntrySummary
            key={entry.id}
            kind={kind}
            entry={entry}
            title={spec.title(entry)}
            sub={spec.sub(entry)}
            onEdit={() => setEditing(entry.id)}
          />
        ),
      )}
      {!entries.length && <p className="small muted">Nothing here yet.</p>}
      <AddButton onClick={add}>{spec.add}</AddButton>
    </div>
  );
}

function EntryField({
  entry,
  field: [key, label, type, placeholder],
  onChange,
}: {
  entry: Record<string, unknown>;
  field: FieldSpec;
  onChange: (value: string) => void;
}) {
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
    const present = key === 'end' && entry.current === true;
    const id = `${String(entry.id)}-${key}`;
    return (
      <div className={styles.field}>
        <label htmlFor={id}>{label}</label>
        {present ? (
          <input id={id} className={inputClass()} value="Present" disabled />
        ) : (
          <DateInput id={id} value={value} onChange={onChange} />
        )}
      </div>
    );
  }
  return <TextField label={label} value={value} placeholder={placeholder} onChange={onChange} />;
}

function EntrySummary<K extends EntryKind>({
  kind,
  entry,
  title,
  sub,
  onEdit,
}: {
  kind: K;
  entry: EntryOf<K>;
  title: string;
  sub: string;
  onEdit: () => void;
}) {
  const detail = 'detail' in entry ? entry.detail : '';
  const bullets = toBullets(detail);
  return (
    <div className={styles.entry}>
      <div className={styles.entryText}>
        <b>{title}</b>
        {sub && <span>{sub}</span>}
        {kind === 'education' && (entry as Education).coursework && (
          <span className={styles.entryCourse}>Coursework: {(entry as Education).coursework}</span>
        )}
        {kind === 'projects' && !detail ? (
          <span className={styles.thinHint}>
            <Dot tone="amber" />
            No description yet. Forms often ask what your part was and who used it.
          </span>
        ) : (
          bullets.length > 0 && (
            <ul className={styles.bullets}>
              {bullets.map((line, index) => (
                <li key={index}>{line}</li>
              ))}
            </ul>
          )
        )}
      </div>
      <IconButton label={`Edit ${title}`} onClick={onEdit}>
        <Icon name="pencil" size={16} stroke={1.75} />
      </IconButton>
    </div>
  );
}

function AddButton({ onClick, children }: { onClick: () => void; children: string }) {
  return (
    <Button variant="ghost" size="sm" className={styles.add} onClick={onClick}>
      <Icon name="plus" size={16} stroke={2} />
      {children}
    </Button>
  );
}
