/** The name, email, phone and address fields of a profile. */
import { TextField } from '@/components/ui/TextField';
import type { Contact } from '@/lib/profileUpdate';
import styles from './ContactFields.module.css';

interface AddressField {
  key: keyof Contact;
  label: string;
  placeholder: string;
  className: string;
}

const ADDRESS_FIELDS: AddressField[] = [
  {
    key: 'street',
    label: 'Street address',
    placeholder: 'e.g. 412 Main Street',
    className: styles.street,
  },
  {
    key: 'street2',
    label: 'Apt, suite, unit (optional)',
    placeholder: 'e.g. Apt 3B',
    className: styles.street2,
  },
  { key: 'city', label: 'City', placeholder: 'City', className: styles.city },
  { key: 'state', label: 'State', placeholder: 'e.g. NY', className: styles.state },
  { key: 'zip', label: 'ZIP code', placeholder: 'e.g. 12180', className: styles.zip },
  { key: 'country', label: 'Country', placeholder: 'Country', className: styles.country },
];

interface ContactFieldsProps {
  value: Contact;
  onChange: (patch: Partial<Contact>) => void;
}

/** Controlled contact fields; reports each change as a partial patch. */
export function ContactFields({ value, onChange }: ContactFieldsProps) {
  return (
    <div className={styles.contact}>
      <div className={styles.name}>
        <TextField
          label="First name"
          autoComplete="given-name"
          required
          value={value.firstName}
          onChange={(firstName) => onChange({ firstName })}
        />
        <TextField
          label="Middle name (optional)"
          autoComplete="additional-name"
          value={value.middleName}
          onChange={(middleName) => onChange({ middleName })}
        />
        <TextField
          label="Last name"
          autoComplete="family-name"
          required
          value={value.lastName}
          onChange={(lastName) => onChange({ lastName })}
        />
      </div>
      <div className={styles.grid2}>
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
        {ADDRESS_FIELDS.map(({ key, label, placeholder, className }) => (
          <TextField
            key={key}
            className={className}
            label={label}
            placeholder={placeholder}
            value={value[key]}
            onChange={(text) => onChange({ [key]: text })}
          />
        ))}
      </div>
    </div>
  );
}
