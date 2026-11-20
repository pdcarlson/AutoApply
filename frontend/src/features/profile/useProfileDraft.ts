/** Local draft of a profile that saves one section at a time. */
import { useState } from 'react';
import type { Profile, ProfileUpdate } from '@/api/types';
import { useUpdateProfile } from '@/api/queries';
import { useToast } from '@/app/providers/toast';
import { toProfileUpdate } from '@/lib/profileUpdate';

const DEFAULT_SAVED_MESSAGE = 'Saved. The next application uses these.';

/** Holds unsaved edits and saves chosen fields on top of what the server has. */
export function useProfileDraft(profile: Profile) {
  const notify = useToast();
  const save = useUpdateProfile();
  const [draft, setDraft] = useState<ProfileUpdate>(() => toProfileUpdate(profile));

  const patch = (changes: Partial<ProfileUpdate>) =>
    setDraft((current) => ({ ...current, ...changes }));

  // Saving on top of the server copy keeps other sections' edits as drafts.
  const saveFields = (changes: Partial<ProfileUpdate>, message = DEFAULT_SAVED_MESSAGE) => {
    patch(changes);
    save.mutate({ ...toProfileUpdate(profile), ...changes }, { onSuccess: () => notify(message) });
  };

  return { draft, patch, saveFields, isSaving: save.isPending };
}
