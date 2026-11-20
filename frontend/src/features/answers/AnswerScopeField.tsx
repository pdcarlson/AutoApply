/** The "Use it for" choice: every company, or only one. */
import { Choice } from '@/components/ui/Choice';
import { inputClass } from '@/components/ui/classNames';
import type { AnswerScope } from './useAnswerForm';
import styles from './AnswerScopeField.module.css';

interface AnswerScopeFieldProps {
  scope: AnswerScope;
  company: string;
  /** The company a saved answer is already limited to, which can't be changed here. */
  savedCompany: string | null;
  /** Companies to pick from; when empty, the company is typed instead. */
  companies: string[];
  onScopeChange: (scope: AnswerScope) => void;
  onCompanyChange: (company: string) => void;
}

/** Two radios, plus a company picker when a new company-only answer is chosen. */
export function AnswerScopeField({
  scope,
  company,
  savedCompany,
  companies,
  onScopeChange,
  onCompanyChange,
}: AnswerScopeFieldProps) {
  const isPickingCompany = scope === 'company' && !savedCompany;
  return (
    <div className={styles.group} role="radiogroup" aria-labelledby="answer-scope">
      <span id="answer-scope" className="eyebrow">
        Use it for
      </span>
      <Choice
        type="radio"
        name="answer-scope"
        checked={scope === 'all'}
        onChange={() => onScopeChange('all')}
      >
        Every company that asks
      </Choice>
      <Choice
        type="radio"
        name="answer-scope"
        checked={scope === 'company'}
        onChange={() => onScopeChange('company')}
      >
        {savedCompany ? `Only ${savedCompany}` : 'Only one company'}
      </Choice>
      {isPickingCompany && (
        <>
          <label className="sr-only" htmlFor="answer-company">
            Company
          </label>
          {companies.length ? (
            <select
              id="answer-company"
              className={inputClass()}
              value={company}
              onChange={(event) => onCompanyChange(event.target.value)}
            >
              {companies.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          ) : (
            <input
              id="answer-company"
              className={inputClass()}
              placeholder="Company name"
              value={company}
              onChange={(event) => onCompanyChange(event.target.value)}
            />
          )}
        </>
      )}
    </div>
  );
}
