/** Form state for adding or editing one saved answer. */
import { useState } from 'react';
import type { Answer, AnswerCategory } from '@/api/types';
import { useCreateAnswer, useDeleteAnswer, useUpdateAnswer } from '@/api/queries';
import { useToast } from '@/app/providers/toast';
import { useKnownCompanies } from './useKnownCompanies';

/** Whether an answer is used everywhere or for one company only. */
export type AnswerScope = 'all' | 'company';

interface AnswerFormCallbacks {
  onSaved: (id: string) => void;
  onDeleted: () => void;
}

/** Holds the edited fields and saves or deletes the answer (`null` when adding one). */
export function useAnswerForm(answer: Answer | null, { onSaved, onDeleted }: AnswerFormCallbacks) {
  const notify = useToast();
  const companies = useKnownCompanies();
  const create = useCreateAnswer();
  const update = useUpdateAnswer();
  const remove = useDeleteAnswer();
  const [question, setQuestion] = useState(answer?.question ?? '');
  const [text, setText] = useState(answer?.answer ?? '');
  const [category, setCategory] = useState<AnswerCategory>(answer?.category ?? 'Experience');
  const [scope, setScope] = useState<AnswerScope>(answer?.company ? 'company' : 'all');
  const [pickedCompany, setCompany] = useState(answer?.company ?? '');
  // The company list loads separately; until one is picked, the select shows the first.
  const company = pickedCompany || companies[0] || '';

  const chosenCompany = scope === 'company' ? company || null : null;
  const hasChanges =
    answer === null ||
    question !== answer.question ||
    text !== answer.answer ||
    chosenCompany !== answer.company;
  const canSave = Boolean(
    hasChanges && question.trim() && text.trim() && (scope === 'all' || chosenCompany),
  );

  const save = () => {
    const input = {
      category,
      question: question.trim(),
      answer: text.trim(),
      company: chosenCompany,
    };
    const onSuccess = (saved: Answer) => {
      notify('Saved. The agent uses it from the next application on.');
      onSaved(saved.id);
    };
    if (answer === null) create.mutate(input, { onSuccess });
    else update.mutate({ id: answer.id, patch: input }, { onSuccess });
  };

  const deleteAnswer = (id: string) =>
    remove.mutate(id, {
      onSuccess: () => {
        notify('Deleted. The agent will ask you again when a form needs it.');
        onDeleted();
      },
    });

  return {
    fields: { question, text, category, scope, company },
    setters: { setQuestion, setText, setCategory, setScope, setCompany },
    companies,
    canSave,
    save,
    isSaving: create.isPending || update.isPending,
    deleteAnswer,
    isDeleting: remove.isPending,
  };
}
