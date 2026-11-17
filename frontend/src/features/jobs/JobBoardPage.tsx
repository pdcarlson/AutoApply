import { useState } from 'react';
import { Link, useNavigate } from 'react-router';
import type { Posting } from '@/api/types';
import { useApplyToPostings, usePostings, useSession } from '@/api/queries';
import { inboxJob, paths } from '@/app/paths';
import { useOverlays } from '@/app/providers/overlays';
import { useToast } from '@/app/providers/toast';
import { Chip } from '@/components/ui/Badges';
import { Button } from '@/components/ui/Button';
import {
  Empty,
  FilterChips,
  Loading,
  LoadError,
  type FilterOption,
} from '@/components/ui/DataDisplay';
import { Icon } from '@/components/ui/Icon';
import { Page, PageTitle } from '@/layouts/Page';
import { daysAgo, formatDateTime, plural } from '@/lib/format';
import styles from './JobBoardPage.module.css';

type Filter = 'all' | 'internship' | 'full_time';

const FILTERS: FilterOption<Filter>[] = [
  { key: 'all', label: 'All' },
  { key: 'internship', label: 'Internships' },
  { key: 'full_time', label: 'Full-time' },
];

const matchesFilter = (posting: Posting, filter: Filter) =>
  filter === 'all' || posting.internship === (filter === 'internship');

const matchesSearch = (posting: Posting, term: string) =>
  !term || [posting.company, posting.role, posting.location].join(' ').toLowerCase().includes(term);

/** Open postings from Greenhouse and Ashby boards, best fit for the profile first. */
export function JobBoardPage() {
  const board = usePostings();
  const session = useSession();
  const apply = useApplyToPostings();
  const notify = useToast();
  const navigate = useNavigate();
  const { open } = useOverlays();
  const [filter, setFilter] = useState<Filter>('all');
  const [search, setSearch] = useState('');
  const [checkedIds, setCheckedIds] = useState<string[]>([]);

  const all = board.data?.postings ?? [];
  const term = search.trim().toLowerCase();
  const visible = all.filter((p) => matchesFilter(p, filter) && matchesSearch(p, term));
  const collecting = board.data?.refreshing && !all.length;
  const selected = all.filter((p) => p.status === 'open' && checkedIds.includes(p.id));

  const toggleChecked = (id: string) =>
    setCheckedIds((ids) => (ids.includes(id) ? ids.filter((each) => each !== id) : [...ids, id]));

  const applyTo = (postings: Posting[]) => {
    if (!postings.length) return;
    if (!session.data?.profileConfirmed) {
      open({ type: 'confirmProfile' });
      return;
    }
    apply.mutate(
      postings.map((p) => p.id),
      {
        onSuccess: ({ started, failed }) => {
          setCheckedIds([]);
          const waiting = started.filter((result) => result.deferred).length;
          const parts = [
            started.length &&
              `Filling ${plural(started.length, 'job', 'jobs')}. You’ll review each one before it’s submitted.`,
            waiting && `${waiting} wait until tomorrow because of your daily limit.`,
            failed.length &&
              `${plural(failed.length, 'posting', 'postings')} couldn’t be added. ${failed[0]}`,
          ];
          const [first] = started;
          notify(parts.filter(Boolean).join(' '), {
            action: first && {
              label: 'Show in Inbox',
              run: () => navigate(started.length === 1 ? inboxJob(first.job.id) : paths.inbox),
            },
          });
        },
      },
    );
  };

  return (
    <Page className={styles.page}>
      <PageTitle
        title="Jobs"
        meta={
          board.data?.fetchedAt
            ? `${plural(all.length, 'posting', 'postings')} · updated ${formatDateTime(board.data.fetchedAt)}`
            : undefined
        }
        lede="Open jobs from company boards on Greenhouse and Ashby, with the best fit for your profile first. Apply fills the form and stops for your review, the same as a pasted link."
      />
      <div className={styles.tools}>
        <label className={styles.search} htmlFor="posting-search">
          <Icon name="search" size={16} stroke={2} />
          <span className="sr-only">Search company, role or place</span>
          <input
            id="posting-search"
            type="search"
            placeholder="Search company, role or place"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <FilterChips<Filter>
          label="Filter by kind of job"
          value={filter}
          onChange={setFilter}
          options={FILTERS.map((option) => ({
            ...option,
            count: all.filter((p) => matchesFilter(p, option.key)).length,
          }))}
        />
        <div className={styles.toolsActions}>
          <span className={styles.applyCount}>{selected.length} selected</span>
          <Button
            variant="primary"
            disabled={!selected.length}
            loading={apply.isPending}
            onClick={() => applyTo(selected)}
          >
            {selected.length ? `Apply to ${selected.length}` : 'Apply'}
          </Button>
        </div>
      </div>
      {board.isPending || collecting ? (
        <Loading label="Collecting postings from the job boards…" />
      ) : board.isError ? (
        <LoadError what="the job board" onRetry={() => board.refetch()} />
      ) : visible.length ? (
        <ul className={styles.list}>
          <li className={`${styles.row} ${styles.listHead}`} aria-hidden="true">
            <span />
            <span className={styles.fit}>Fit</span>
            <span className={styles.main}>Job</span>
            <span className={styles.why}>Why it fits</span>
            <span className={styles.actions} />
          </li>
          {visible.map((posting) => (
            <PostingRow
              key={posting.id}
              posting={posting}
              checked={selected.includes(posting)}
              applying={apply.isPending}
              onToggleChecked={() => toggleChecked(posting.id)}
              onApply={() => applyTo([posting])}
            />
          ))}
        </ul>
      ) : (
        <Empty>
          {all.length
            ? 'No postings match that search.'
            : 'No postings came back from the job boards. Check your connection and reload.'}
        </Empty>
      )}
    </Page>
  );
}

interface PostingRowProps {
  posting: Posting;
  checked: boolean;
  applying: boolean;
  onToggleChecked: () => void;
  onApply: () => void;
}

function PostingRow({ posting, checked, applying, onToggleChecked, onApply }: PostingRowProps) {
  return (
    <li className={styles.row}>
      <input
        type="checkbox"
        className={styles.check}
        aria-label={`Select ${posting.company}, ${posting.role}`}
        checked={checked}
        disabled={posting.status !== 'open'}
        onChange={onToggleChecked}
      />
      <span className={styles.fit} title="How well it fits your profile, out of 100">
        <b>{posting.fit.score}</b>
      </span>
      <div className={styles.main}>
        <b>
          {posting.company} · {posting.role}
        </b>
        <span className={styles.sub}>
          {[
            posting.location,
            posting.ats,
            posting.postedAt && `Posted ${daysAgo(posting.postedAt)}`,
          ]
            .filter(Boolean)
            .join(' · ')}
        </span>
      </div>
      <span className={styles.why}>
        {posting.fit.reasons.join(' · ') || 'Nothing on your profile matches it yet'}
      </span>
      <div className={styles.actions}>
        <a className="small" href={posting.url} target="_blank" rel="noopener noreferrer">
          Open posting
        </a>
        {posting.status === 'applied' ? (
          <Chip tone="grey">Applied</Chip>
        ) : posting.status === 'in_inbox' && posting.jobId ? (
          <Link className="small" to={inboxJob(posting.jobId)}>
            In your Inbox
          </Link>
        ) : (
          <Button
            size="sm"
            variant="primary"
            aria-label={`Apply to ${posting.company}, ${posting.role}`}
            disabled={applying}
            onClick={onApply}
          >
            Apply
          </Button>
        )}
      </div>
    </li>
  );
}
