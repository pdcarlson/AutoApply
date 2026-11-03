import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { ANSWER_CATEGORIES, type Answer, type AnswerCategory } from '@/api/types';
import { useAnswers, useJobs } from '@/api/queries';
import { inboxJob } from '@/app/paths';
import { Dot, MiniTag } from '@/components/ui/Badges';
import { Button } from '@/components/ui/Button';
import { Banner } from '@/components/ui/Callouts';
import { Empty, FilterChips, Loading, LoadError } from '@/components/ui/DataDisplay';
import { Icon } from '@/components/ui/Icon';
import { PageTitle } from '@/layouts/Page';
import { formatDay, plural } from '@/lib/format';
import { cx } from '@/lib/cx';
import { AnswerDetail } from './AnswerDetail';
import styles from './AnswerBankPage.module.css';

type Category = 'All' | AnswerCategory;

const matchesSearch = (answer: Answer, term: string) =>
  !term ||
  [answer.question, answer.answer, ...answer.alsoMatches.map((m) => m.wording)]
    .join(' ')
    .toLowerCase()
    .includes(term);

/** `null` = nothing picked yet (first answer shows), `'new'` = adding one. */
type Selection = string | 'new' | null;

export function AnswerBankPage() {
  const answers = useAnswers();
  const jobs = useJobs();
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState<Category>('All');
  const [selection, setSelection] = useState<Selection>(null);

  const all = answers.data ?? [];
  const term = search.trim().toLowerCase();
  const visible = all.filter(
    (a) => (category === 'All' || a.category === category) && matchesSearch(a, term),
  );
  const selected =
    selection === 'new' ? null : (all.find((a) => a.id === selection) ?? all[0] ?? null);
  const waiting = (jobs.data ?? []).filter((job) => job.state === 'needs_input' && job.question);
  const showDetail = selection === 'new' || selected !== null;

  // On phones the detail sits under the list; bring it into view when one is picked.
  useEffect(() => {
    if (selection && window.innerWidth < 900) {
      document.getElementById('answer-detail')?.scrollIntoView({ block: 'start' });
    }
  }, [selection]);

  return (
    <div className={cx(styles.layout, showDetail && styles.withDetail)}>
      <main id="main" className={styles.main}>
        <div className={styles.head}>
          <PageTitle
            title="Answer bank"
            meta={plural(all.length, 'answer', 'answers')}
            lede="Answer once. The agent reuses these on every form that asks the same thing, even when it’s worded differently. Company-specific answers are only used for that company."
            action={
              <Button
                size="sm"
                onClick={() => {
                  setSearch('');
                  setCategory('All');
                  setSelection('new');
                }}
              >
                <Icon name="plus" size={16} />
                Add answer
              </Button>
            }
          />
          {waiting.length > 0 && (
            <Banner
              tone="amber"
              leading={<Dot tone="amber" />}
              title={`${plural(waiting.length, 'question', 'questions')} waiting for an answer`}
              action={
                <Button size="sm" onClick={() => navigate(inboxJob(waiting[0].id))}>
                  Answer in Inbox
                </Button>
              }
            >
              {waiting[0].company}’s form asks: “{waiting[0].question!.field}”
            </Banner>
          )}
          <div className={styles.tools}>
            <label className={styles.search} htmlFor="answer-search">
              <Icon name="search" size={16} stroke={2} />
              <span className="sr-only">Search questions and answers</span>
              <input
                id="answer-search"
                type="search"
                placeholder="Search questions and answers"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </label>
            <FilterChips<Category>
              label="Filter by category"
              value={category}
              onChange={setCategory}
              options={(['All', ...ANSWER_CATEGORIES] as Category[]).map((key) => ({
                key,
                label: key,
                count: key === 'All' ? all.length : all.filter((a) => a.category === key).length,
              }))}
            />
          </div>
        </div>

        <div className={styles.table}>
          <div className={cx(styles.grid, styles.tableHead)} aria-hidden="true">
            <span>Question</span>
            <span>Your answer</span>
            <span className={styles.right}>Used</span>
          </div>
          <div className={styles.tableBody}>
            {answers.isPending ? (
              <Loading />
            ) : answers.isError ? (
              <LoadError what="your answers" onRetry={() => answers.refetch()} />
            ) : visible.length ? (
              visible.map((answer) => (
                <button
                  key={answer.id}
                  type="button"
                  className={cx(styles.grid, styles.row, answer.id === selected?.id && styles.on)}
                  aria-pressed={answer.id === selected?.id}
                  onClick={() => setSelection(answer.id)}
                >
                  <span className={styles.question}>
                    <b>{answer.question}</b>
                    <span className={styles.meta}>
                      <span>{answer.category}</span>
                      {answer.company && <MiniTag>Only {answer.company}</MiniTag>}
                      {answer.savedRecently && <MiniTag filled>Saved today</MiniTag>}
                    </span>
                  </span>
                  <span className={styles.answer}>{answer.answer || '—'}</span>
                  <span className={styles.used}>
                    <b>{answer.timesUsed}×</b>
                    <span>{answer.lastUsedAt ? formatDay(answer.lastUsedAt) : 'Not used yet'}</span>
                  </span>
                </button>
              ))
            ) : (
              <Empty>
                {all.length
                  ? `No answers match “${search}”.`
                  : 'No saved answers yet. They build up as you answer the agent’s questions.'}
              </Empty>
            )}
          </div>
        </div>
      </main>
      {selection === 'new' ? (
        <AnswerDetail
          key="new"
          answer={null}
          onSaved={setSelection}
          onDeleted={() => setSelection(null)}
        />
      ) : (
        selected && (
          <AnswerDetail
            key={selected.id}
            answer={selected}
            onSaved={setSelection}
            onDeleted={() => setSelection(null)}
          />
        )
      )}
    </div>
  );
}
