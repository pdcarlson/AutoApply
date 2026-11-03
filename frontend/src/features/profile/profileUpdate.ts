import type { Profile, ProfileUpdate } from '@/api/types';

/** The editable part of a profile, as sent back with PUT /profile. */
export function toProfileUpdate(profile: Profile): ProfileUpdate {
  const { resume, unplaced, ...editable } = profile;
  return editable;
}
