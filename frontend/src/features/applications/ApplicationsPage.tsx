/** The Applications screen: what's ready to submit and everything already sent. */
import { useSearchParams } from 'react-router';
import { useApplications, useJobs } from '@/api/queries';
import { FilterChips } from '@/components/ui/FilterChips';
import { Empty, Loading, LoadError } from '@/components/ui/LoadStates';
import { Page, PageTitle } from '@/layouts/Page';
import { byNewest } from '@/lib/jobStatus';
import { filterOptions, parseFilter, rowsFor } from './applicationFilters';
import { ApplicationList } from './ApplicationList';
import styles from './ApplicationsPage.module.css';

/** Lists ready jobs and submitted applications, filtered by status. */
export function ApplicationsPage() {
  const applications = useApplications();
  const jobs = useJobs();
  const [params, setParams] = useSearchParams();
  const filter = parseFilter(params.get('filter'));

  const ready = (jobs.data ?? []).filter((job) => job.state === 'ready').sort(byNewest);
  const sent = applications.data ?? [];
  const rows = rowsFor(filter, ready, sent);
  const emptyMessage =
    filter === 'ready'
      ? 'Nothing is waiting for your approval. When the agent finishes filling a form, it shows up here.'
      : 'No applications with this status yet.';

  return (
    <Page className={styles.page}>
      <PageTitle
        title="Applications"
        meta={`${ready.length} ready to submit · ${sent.length} submitted`}
      />
      <FilterChips
        label="Filter by status"
        value={filter}
        onChange={(key) => setParams(key === 'all' ? {} : { filter: key }, { replace: true })}
        options={filterOptions(ready, sent)}
      />
      {applications.isPending || jobs.isPending ? (
        <Loading />
      ) : applications.isError ? (
        <LoadError what="your applications" onRetry={() => applications.refetch()} />
      ) : rows.readyJobs.length || rows.applications.length ? (
        <ApplicationList readyJobs={rows.readyJobs} applications={rows.applications} />
      ) : (
        <Empty>{emptyMessage}</Empty>
      )}
    </Page>
  );
}
