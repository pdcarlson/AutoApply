/** The Inbox's filter chips and bulk Apply button. */
import type { Job } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { FilterChips } from '@/components/ui/FilterChips';
import { filterOptions, type InboxFilter } from './inboxFilters';
import styles from './InboxToolbar.module.css';

interface InboxToolbarProps {
  jobs: Job[];
  filter: InboxFilter;
  onFilterChange: (filter: InboxFilter) => void;
  checkedCount: number;
  applying: boolean;
  onApply: () => void;
}

/** Filters on the left; the checked count and "Apply to N" on the right. */
export function InboxToolbar({
  jobs,
  filter,
  onFilterChange,
  checkedCount,
  applying,
  onApply,
}: InboxToolbarProps) {
  return (
    <div className={styles.toolbar}>
      <FilterChips
        label="Show"
        value={filter}
        onChange={onFilterChange}
        options={filterOptions(jobs)}
      />
      <div className={styles.toolbarActions}>
        <span className={styles.applyCount}>{checkedCount} selected</span>
        <Button variant="primary" disabled={!checkedCount} loading={applying} onClick={onApply}>
          {checkedCount ? `Apply to ${checkedCount}` : 'Apply'}
        </Button>
      </div>
    </div>
  );
}
