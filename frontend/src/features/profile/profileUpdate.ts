import type { Profile, ProfileUpdate } from '@/api/types';

/** The editable part of a profile, as sent back with PUT /profile. */
export function toProfileUpdate(profile: Profile): ProfileUpdate {
  const { resume, unplaced, ...editable } = profile;
  return editable;
}

/** What's missing from the required name fields (first and last; middle is optional), or null. */
export function missingName({
  firstName,
  lastName,
}: Pick<ProfileUpdate, 'firstName' | 'lastName'>) {
  const first = !firstName.trim();
  const last = !lastName.trim();
  if (first && last) return 'first and last name';
  if (first) return 'first name';
  if (last) return 'last name';
  return null;
}
