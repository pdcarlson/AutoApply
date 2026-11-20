/** Draft of the profile during setup review, including resolving unplaced resume text. */
import { useState } from 'react';
import type { Profile, ProfileUpdate, UnplacedSection } from '@/api/types';
import { useResolveUnplaced, useUpdateProfile } from '@/api/queries';
import { toProfileUpdate } from '@/lib/profileUpdate';
import type { UnplacedAction } from './UnplacedCard';

/** Holds the edited profile and keeps the list of unplaced sections current. */
export function useReviewDraft(profile: Profile) {
  const save = useUpdateProfile();
  const resolve = useResolveUnplaced();
  const [draft, setDraft] = useState<ProfileUpdate>(() => toProfileUpdate(profile));

  const patch = (changes: Partial<ProfileUpdate>) =>
    setDraft((current) => ({ ...current, ...changes }));

  // Accepting moves resume text into the profile on the server, so save edits first, then
  // take the server's merged result as the new draft.
  const resolveUnplaced = async (section: UnplacedSection, action: UnplacedAction) => {
    await save.mutateAsync(draft);
    const updated = await resolve.mutateAsync({ id: section.id, action });
    setDraft(toProfileUpdate(updated));
  };

  return {
    draft,
    patch,
    resolveUnplaced,
    save,
    unplaced: resolve.data?.unplaced ?? save.data?.unplaced ?? profile.unplaced,
    isResolving: resolve.isPending || save.isPending,
  };
}
