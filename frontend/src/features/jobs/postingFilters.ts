/** Search and kind-of-job filtering for the job board. */
import type { Posting } from '@/api/types';
import type { FilterOption } from '@/components/ui/FilterChips';

/** The job board's filter chips. */
export type PostingFilter = 'all' | 'internship' | 'full_time';

const FILTERS: FilterOption<PostingFilter>[] = [
  { key: 'all', label: 'All' },
  { key: 'internship', label: 'Internships' },
  { key: 'full_time', label: 'Full-time' },
];

const matchesFilter = (posting: Posting, filter: PostingFilter) =>
  filter === 'all' || posting.internship === (filter === 'internship');

const matchesSearch = (posting: Posting, term: string) =>
  !term || [posting.company, posting.role, posting.location].join(' ').toLowerCase().includes(term);

/** The postings that pass both the filter and the search. */
export function filterPostings(postings: Posting[], filter: PostingFilter, search: string) {
  const term = search.trim().toLowerCase();
  return postings.filter(
    (posting) => matchesFilter(posting, filter) && matchesSearch(posting, term),
  );
}

/** The filter chips, each with how many postings it holds. */
export function postingFilterOptions(postings: Posting[]) {
  return FILTERS.map((option) => ({
    ...option,
    count: postings.filter((posting) => matchesFilter(posting, option.key)).length,
  }));
}
