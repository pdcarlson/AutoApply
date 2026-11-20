/** The Answer bank screen: saved answers the agent reuses, with a detail panel. */
import { useEffect, useState } from 'react';
import type { Answer } from '@/api/types';
import { useAnswers } from '@/api/queries';
import { Button } from '@/components/ui/Button';
import { FilterChips } from '@/components/ui/FilterChips';
import { Empty, Loading, LoadError } from '@/components/ui/LoadStates';
import { Icon } from '@/components/ui/Icon';
import { PageTitle } from '@/layouts/Page';
import { plural } from '@/lib/format';
import { cx } from '@/lib/cx';
import { AnswerDetail } from './AnswerDetail';
import { categoryOptions, filterAnswers, type CategoryFilter } from './answerFilters';
import { AnswerTable } from './AnswerTable';
import { WaitingQuestionBanner } from './WaitingQuestionBanner';
import styles from './AnswerBankPage.module.css';

/** Below this width the detail sits under the list instead of beside it. */
const PHONE_MAX_WIDTH_PX = 900;

const LEDE =
  'Answer once. The agent reuses these on every form that asks the same thing, even when it’s worded differently. Company-specific answers are only used for that company.';

/** `null` = nothing picked yet (first answer shows), `'new'` = adding one. */
type Selection = string | 'new' | null;

/** On phones, scrolls the detail into view whenever an answer is picked. */
function useScrollDetailIntoView(selection: Selection) {
  useEffect(() => {
    if (selection && window.innerWidth < PHONE_MAX_WIDTH_PX) {
      document.getElementById('answer-detail')?.scrollIntoView({ block: 'start' });
    }
  }, [selection]);
}

/** Search, filter and pick saved answers; the picked one opens beside the list. */
export function AnswerBankPage() {
  const answers = useAnswers();
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState<CategoryFilter>('All');
  const [selection, setSelection] = useState<Selection>(null);
  useScrollDetailIntoView(selection);

  const all = answers.data ?? [];
  const visible = filterAnswers(all, category, search);
  const selected: Answer | null =
    selection === 'new' ? null : (all.find((answer) => answer.id === selection) ?? all[0] ?? null);
  const isDetailShown = selection === 'new' || selected !== null;

  const startNewAnswer = () => {
    setSearch('');
    setCategory('All');
    setSelection('new');
  };

  const emptyMessage = all.length
    ? `No answers match “${search}”.`
    : 'No saved answers yet. They build up as you answer the agent’s questions.';
  const placeholder = answers.isPending ? (
    <Loading />
  ) : answers.isError ? (
    <LoadError what="your answers" onRetry={() => answers.refetch()} />
  ) : visible.length ? null : (
    <Empty>{emptyMessage}</Empty>
  );

  return (
    <div className={cx(styles.layout, isDetailShown && styles.withDetail)}>
      <main id="main" className={styles.main}>
        <div className={styles.head}>
          <PageTitle
            title="Answer bank"
            meta={plural(all.length, 'answer', 'answers')}
            lede={LEDE}
            action={
              <Button size="sm" onClick={startNewAnswer}>
                <Icon name="plus" size={16} />
                Add answer
              </Button>
            }
          />
          <WaitingQuestionBanner />
          <div className={styles.tools}>
            <label className={styles.search} htmlFor="answer-search">
              <Icon name="search" size={16} stroke={2} />
              <span className="sr-only">Search questions and answers</span>
              <input
                id="answer-search"
                type="search"
                placeholder="Search questions and answers"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </label>
            <FilterChips<CategoryFilter>
              label="Filter by category"
              value={category}
              onChange={setCategory}
              options={categoryOptions(all)}
            />
          </div>
        </div>
        <AnswerTable
          answers={visible}
          selectedId={selected?.id}
          onSelect={setSelection}
          placeholder={placeholder}
        />
      </main>
      {isDetailShown && (
        <AnswerDetail
          key={selected?.id ?? 'new'}
          answer={selected}
          onSaved={setSelection}
          onDeleted={() => setSelection(null)}
        />
      )}
    </div>
  );
}
