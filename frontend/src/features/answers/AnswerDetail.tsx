/** Side panel for adding, editing or deleting one saved answer. */
import { ANSWER_CATEGORIES, type Answer, type AnswerCategory } from '@/api/types';
import { Note } from '@/components/ui/Callouts';
import { inputClass } from '@/components/ui/classNames';
import { cx } from '@/lib/cx';
import { AnswerDetailFooter } from './AnswerDetailFooter';
import { AnswerHistory } from './AnswerHistory';
import { AnswerScopeField } from './AnswerScopeField';
import { useAnswerForm } from './useAnswerForm';
import styles from './AnswerDetail.module.css';

interface AnswerDetailProps {
  /** Null when adding a new answer. */
  answer: Answer | null;
  onSaved: (id: string) => void;
  onDeleted: () => void;
}

/** The answer's question, text and scope, with its history once it's saved. */
export function AnswerDetail({ answer, onSaved, onDeleted }: AnswerDetailProps) {
  const form = useAnswerForm(answer, { onSaved, onDeleted });
  const { question, text, category, scope, company } = form.fields;
  const { setQuestion, setText, setCategory, setScope, setCompany } = form.setters;

  return (
    <aside
      className={styles.detail}
      aria-label={answer ? 'Selected answer' : 'New answer'}
      id="answer-detail"
    >
      <div className={styles.detailBody}>
        <div className={styles.group}>
          {answer ? (
            <>
              <span className="eyebrow">{answer.category}</span>
              <h2 className="h3">{answer.question}</h2>
            </>
          ) : (
            <>
              <label className="eyebrow" htmlFor="answer-category">
                Category
              </label>
              <select
                id="answer-category"
                className={inputClass()}
                value={category}
                onChange={(event) => setCategory(event.target.value as AnswerCategory)}
              >
                {ANSWER_CATEGORIES.map((option) => (
                  <option key={option} value={option}>
                    {option}
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
                onChange={(event) => setQuestion(event.target.value)}
              />
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
            className={cx(inputClass(), styles.textarea)}
            rows={4}
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
        </div>

        <AnswerScopeField
          scope={scope}
          company={company}
          savedCompany={answer?.company ?? null}
          companies={form.companies}
          onScopeChange={setScope}
          onCompanyChange={setCompany}
        />

        {answer && <AnswerHistory answer={answer} />}
      </div>

      <AnswerDetailFooter
        isNew={answer === null}
        canSave={form.canSave}
        isSaving={form.isSaving}
        isDeleting={form.isDeleting}
        onSave={form.save}
        onDelete={() => answer && form.deleteAnswer(answer.id)}
        onCancel={onDeleted}
      />
    </aside>
  );
}
