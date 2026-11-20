/** The Jobs screen: open postings from company job boards, best fit first. */
import { useState } from 'react';
import type { Posting } from '@/api/types';
import { usePostings } from '@/api/queries';
import { Button } from '@/components/ui/Button';
import { FilterChips } from '@/components/ui/FilterChips';
import { Icon } from '@/components/ui/Icon';
import { Empty, Loading, LoadError } from '@/components/ui/LoadStates';
import { Page, PageTitle } from '@/layouts/Page';
import { formatDateTime, plural } from '@/lib/format';
import { filterPostings, postingFilterOptions, type PostingFilter } from './postingFilters';
import { PostingList } from './PostingList';
import { usePostingApply } from './usePostingApply';
import styles from './JobBoardPage.module.css';

const LEDE =
  'Open jobs from company boards on Greenhouse and Ashby, with the best fit for your profile first. Apply fills the form and stops for your review, the same as a pasted link.';

/** Open postings from Greenhouse and Ashby boards, best fit for the profile first. */
export function JobBoardPage() {
  const board = usePostings();
  const [filter, setFilter] = useState<PostingFilter>('all');
  const [search, setSearch] = useState('');
  const [checkedIds, setCheckedIds] = useState<string[]>([]);
  const { applyTo, isApplying } = usePostingApply(() => setCheckedIds([]));

  const all = board.data?.postings ?? [];
  const visible = filterPostings(all, filter, search);
  const isCollecting = board.data?.refreshing && !all.length;
  const selected = all.filter(
    (posting) => posting.status === 'open' && checkedIds.includes(posting.id),
  );
  const meta = board.data?.fetchedAt
    ? `${plural(all.length, 'posting', 'postings')} · updated ${formatDateTime(board.data.fetchedAt)}`
    : undefined;

  const toggleChecked = (posting: Posting) =>
    setCheckedIds((ids) =>
      ids.includes(posting.id) ? ids.filter((id) => id !== posting.id) : [...ids, posting.id],
    );

  return (
    <Page className={styles.page}>
      <PageTitle title="Jobs" meta={meta} lede={LEDE} />
      <div className={styles.tools}>
        <label className={styles.search} htmlFor="posting-search">
          <Icon name="search" size={16} stroke={2} />
          <span className="sr-only">Search company, role or place</span>
          <input
            id="posting-search"
            type="search"
            placeholder="Search company, role or place"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <FilterChips<PostingFilter>
          label="Filter by kind of job"
          value={filter}
          onChange={setFilter}
          options={postingFilterOptions(all)}
        />
        <div className={styles.toolsActions}>
          <span className={styles.applyCount}>{selected.length} selected</span>
          <Button
            variant="primary"
            disabled={!selected.length}
            loading={isApplying}
            onClick={() => applyTo(selected)}
          >
            {selected.length ? `Apply to ${selected.length}` : 'Apply'}
          </Button>
        </div>
      </div>
      {board.isPending || isCollecting ? (
        <Loading label="Collecting postings from the job boards…" />
      ) : board.isError ? (
        <LoadError what="the job board" onRetry={() => board.refetch()} />
      ) : visible.length ? (
        <PostingList
          postings={visible}
          isChecked={(posting) => selected.includes(posting)}
          applying={isApplying}
          onToggleChecked={toggleChecked}
          onApply={(posting) => applyTo([posting])}
        />
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
