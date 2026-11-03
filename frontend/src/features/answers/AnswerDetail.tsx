import { useState } from 'react';
import { ANSWER_CATEGORIES, type Answer, type AnswerCategory } from '@/api/types';
import {
  useApplications,
  useCreateAnswer,
  useDeleteAnswer,
  useJobs,
  useUpdateAnswer,
} from '@/api/queries';
import { useToast } from '@/app/providers/toast';
import { Button } from '@/components/ui/Button';
import { Note } from '@/components/ui/Callouts';
import { Choice } from '@/components/ui/Form';
import { inputClass } from '@/components/ui/classNames';
import { formatDay } from '@/lib/format';
import styles from './AnswerBankPage.module.css';

/** Companies the user has applied to or has in their Inbox, for company-only answers. */
function useKnownCompanies() {
  const apps = useApplications().data ?? [];
  const jobs = useJobs().data ?? [];
  return [...new Set([...apps.map((a) => a.company), ...jobs.map((j) => j.company)])].sort();
}

interface AnswerDetailProps {
  /** Null when adding a new answer. */
  answer: Answer | null;
  onSaved: (id: string) => void;
  onDeleted: () => void;
}

export function AnswerDetail({ answer, onSaved, onDeleted }: AnswerDetailProps) {
  const notify = useToast();
  const companies = useKnownCompanies();
  const create = useCreateAnswer();
  const update = useUpdateAnswer();
  const remove = useDeleteAnswer();
  const [question, setQuestion] = useState(answer?.question ?? '');
  const [text, setText] = useState(answer?.answer ?? '');
  const [category, setCategory] = useState<AnswerCategory>(answer?.category ?? 'Experience');
  const [scope, setScope] = useState<'all' | 'company'>(answer?.company ? 'company' : 'all');
  const [pickedCompany, setCompany] = useState(answer?.company ?? '');
  // The company list loads separately; until one is picked, the select shows the first.
  const company = pickedCompany || companies[0] || '';
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const isNew = answer === null;
  const chosenCompany = scope === 'company' ? company || null : null;
  const changed =
    isNew ||
    question !== answer.question ||
    text !== answer.answer ||
    chosenCompany !== answer.company;
  const canSave = changed && question.trim() && text.trim() && (scope === 'all' || chosenCompany);

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
    if (isNew) create.mutate(input, { onSuccess });
    else update.mutate({ id: answer.id, patch: input }, { onSuccess });
  };

  const confirmDelete = () =>
    remove.mutate(answer!.id, {
      onSuccess: () => {
        notify('Deleted. The agent will ask you again when a form needs it.');
        onDeleted();
      },
    });

  return (
    <aside
      className={styles.detail}
      aria-label={isNew ? 'New answer' : 'Selected answer'}
      id="answer-detail"
    >
      <div className={styles.detailBody}>
        <div className={styles.group}>
          {isNew ? (
            <>
              <label className="eyebrow" htmlFor="answer-category">
                Category
              </label>
              <select
                id="answer-category"
                className={inputClass()}
                value={category}
                onChange={(e) => setCategory(e.target.value as AnswerCategory)}
              >
                {ANSWER_CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
              <label className="eyebrow" htmlFor="answer-question">
                Question
              </label>
              <input
                id="answer-question"
                className={inputClass()}
                placeholder="The question, as forms ask it"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
              />
            </>
          ) : (
            <>
              <span className="eyebrow">{answer.category}</span>
              <h2 className="h3">{answer.question}</h2>
            </>
          )}
        </div>

        {answer?.savedRecently && (
          <Note tone="teal" title="Saved from your reply today">
            {answer.source}
          </Note>
        )}

        <div className={styles.group}>
          <label className="eyebrow" htmlFor="answer-text">
            Answer
          </label>
          <textarea
            id="answer-text"
            className={`${inputClass()} ${styles.textarea}`}
            rows={4}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </div>

        <div className={styles.group} role="radiogroup" aria-labelledby="answer-scope">
          <span id="answer-scope" className="eyebrow">
            Use it for
          </span>
          <Choice
            type="radio"
            name="answer-scope"
            checked={scope === 'all'}
            onChange={() => setScope('all')}
          >
            Every company that asks
          </Choice>
          <Choice
            type="radio"
            name="answer-scope"
            checked={scope === 'company'}
            onChange={() => setScope('company')}
          >
            {answer?.company ? `Only ${answer.company}` : 'Only one company'}
          </Choice>
          {scope === 'company' && !answer?.company && (
            <>
              <label className="sr-only" htmlFor="answer-company">
                Company
              </label>
              {companies.length ? (
                <select
                  id="answer-company"
                  className={inputClass()}
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                >
                  {companies.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  id="answer-company"
                  className={inputClass()}
                  placeholder="Company name"
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                />
              )}
            </>
          )}
        </div>

        {answer && (
          <>
            <div className={styles.group}>
              <span className="eyebrow">
                Also matches{answer.alsoMatches.length ? ` · ${answer.alsoMatches.length}` : ''}
              </span>
              {answer.alsoMatches.length ? (
                answer.alsoMatches.map((match) => (
                  <div key={match.wording} className={styles.match}>
                    <span>“{match.wording}”</span>
                    <span>{match.seenOn}</span>
                  </div>
                ))
              ) : (
                <span className="small muted">No other wording seen yet.</span>
              )}
            </div>
            <div className={styles.group}>
              <span className="eyebrow">
                Used on{answer.usedOn.length ? ` · ${answer.usedOn.length}` : ''}
              </span>
              {answer.usedOn.length ? (
                answer.usedOn.map((use, index) => (
                  <div key={index} className={styles.usedRow}>
                    <span>{use.company}</span>
                    <span>
                      {formatDay(use.at)}
                      {use.note && ` · ${use.note}`}
                    </span>
                  </div>
                ))
              ) : (
                <span className="small muted">Not used yet.</span>
              )}
            </div>
            <div className={styles.group}>
              <span className="eyebrow">Where it came from</span>
              <span className="small ink2">{answer.source}</span>
            </div>
          </>
        )}
      </div>

      <div className={styles.detailFoot}>
        {confirmingDelete && answer ? (
          <div className={styles.confirmDelete}>
            <p className="small">
              <b>Delete this answer?</b> The agent will ask you again the next time a form needs it.
            </p>
            <div className={styles.buttons}>
              <Button
                size="sm"
                variant="dangerSolid"
                loading={remove.isPending}
                onClick={confirmDelete}
              >
                Delete
              </Button>
              <Button size="sm" onClick={() => setConfirmingDelete(false)}>
                Keep it
              </Button>
            </div>
          </div>
        ) : (
          <>
            <Button
              variant="primary"
              size="sm"
              grow
              disabled={!canSave}
              loading={create.isPending || update.isPending}
              onClick={save}
            >
              {isNew ? 'Save answer' : 'Save changes'}
            </Button>
            {answer ? (
              <Button size="sm" variant="danger" onClick={() => setConfirmingDelete(true)}>
                Delete
              </Button>
            ) : (
              <Button size="sm" onClick={onDeleted}>
                Cancel
              </Button>
            )}
          </>
        )}
      </div>
    </aside>
  );
}
