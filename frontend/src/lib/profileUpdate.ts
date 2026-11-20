/** Helpers that turn a loaded profile into the shapes the editors and PUT /profile use. */
import type { Profile, ProfileUpdate } from '@/api/types';

const CONTACT_KEYS = [
  'firstName',
  'middleName',
  'lastName',
  'email',
  'phone',
  'street',
  'street2',
  'city',
  'state',
  'zip',
  'country',
] as const;

/** The contact part of a profile: name, email, phone and address. */
export type Contact = Pick<ProfileUpdate, (typeof CONTACT_KEYS)[number]>;

/** The editable part of a profile, as sent back with PUT /profile. */
export function toProfileUpdate(profile: Profile): ProfileUpdate {
  const { resume, unplaced, ...editable } = profile;
  return editable;
}

/** Copies just the contact fields out of a profile update. */
export function pickContact(update: ProfileUpdate): Contact {
  const contact = {} as Contact;
  for (const key of CONTACT_KEYS) contact[key] = update[key];
  return contact;
}

/** What's missing from the required name fields (first and last; middle is optional), or null. */
export function missingName({
  firstName,
  lastName,
}: Pick<ProfileUpdate, 'firstName' | 'lastName'>) {
  const isFirstMissing = !firstName.trim();
  const isLastMissing = !lastName.trim();
  if (isFirstMissing && isLastMissing) return 'first and last name';
  if (isFirstMissing) return 'first name';
  if (isLastMissing) return 'last name';
  return null;
}
