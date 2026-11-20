/** Draft of the setup questions, and finishing setup with it. */
import { useState } from 'react';
import { useNavigate } from 'react-router';
import type { CommonAnswers, CommonQuestionKey } from '@/api/types';
import { useConfirmProfile, useUpdateCommonAnswers } from '@/api/queries';
import { paths } from '@/app/paths';
import { useToast } from '@/app/providers/toast';

/** Holds unsaved answers; `finish` saves them, confirms the profile and opens the Inbox. */
export function useCommonAnswersDraft(initial: CommonAnswers) {
  const navigate = useNavigate();
  const notify = useToast();
  const save = useUpdateCommonAnswers();
  const confirm = useConfirmProfile();
  const [draft, setDraft] = useState(initial);

  const patch = (changes: Partial<CommonAnswers>) =>
    setDraft((current) => ({ ...current, ...changes }));

  const toggleSkip = (key: CommonQuestionKey) =>
    patch({
      skipped: draft.skipped.includes(key)
        ? draft.skipped.filter((skippedKey) => skippedKey !== key)
        : [...draft.skipped, key],
    });

  const finish = async () => {
    await save.mutateAsync(draft);
    await confirm.mutateAsync();
    navigate(paths.inbox);
    notify('Profile confirmed. Paste a job link to start your first application.');
  };

  return {
    draft,
    patch,
    toggleSkip,
    finish,
    error: save.error ?? confirm.error,
    isFinishing: save.isPending || confirm.isPending,
  };
}
