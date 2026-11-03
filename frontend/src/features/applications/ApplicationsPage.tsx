import { useSearchParams } from 'react-router';
import type { Application, ApplicationStatus, Job } from '@/api/types';
import { useApplications, useJobs } from '@/api/queries';
import { useOverlays } from '@/app/providers/overlays';
import { Chip } from '@/components/ui/Badges';
import { Button, LinkButton } from '@/components/ui/Button';
import { Empty, FilterChips, Loading, LoadError } from '@/components/ui/DataDisplay';
import { Icon } from '@/components/ui/Icon';
import { Page, PageTitle } from '@/layouts/Page';
import { APPLICATION_STATUSES, APPLICATION_STATUS_LABELS, byNewest } from '@/lib/jobStatus';
import { daysAgo, formatDateTime, formatDay, formatTime } from '@/lib/format';
import { cx } from '@/lib/cx';
import { useStatusChange } from './useStatusChange';
import styles from './ApplicationsPage.module.css';

type Filter = 'all' | 'ready' | ApplicationStatus;

const FILTER_LABELS: [Filter, string][] = [
  ['all', 'All'],
  ['ready', 'Ready to submit'],
  ...APPLICATION_STATUSES.map((s) => [s, APPLICATION_STATUS_LABELS[s]] as [Filter, string]),
];

const isFilter = (value: string | null): value is Filter =>
  FILTER_LABELS.some(([key]) => key === value);

export function ApplicationsPage() {
  const apps = useApplications();
  const jobs = useJobs();
  const [params, setParams] = useSearchParams();
  const filterParam = params.get('filter');
  const filter: Filter = isFilter(filterParam) ? filterParam : 'all';

  const ready = (jobs.data ?? []).filter((job) => job.state === 'ready').sort(byNewest);
  const sent = apps.data ?? [];
  const counts: Record<Filter, number> = {
    all: ready.length + sent.length,
    ready: ready.length,
    ...(Object.fromEntries(
      APPLICATION_STATUSES.map((s) => [s, sent.filter((app) => app.status === s).length]),
    ) as Record<ApplicationStatus, number>),
  };

  const readyRows = filter === 'all' || filter === 'ready' ? ready : [];
  const appRows =
    filter === 'all' ? sent : filter === 'ready' ? [] : sent.filter((app) => app.status === filter);

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
        options={FILTER_LABELS.map(([key, label]) => ({
          key,
          label,
          count: counts[key],
          dot: key === 'ready' && counts.ready > 0 ? 'mark' : null,
        }))}
      />
      {apps.isPending || jobs.isPending ? (
        <Loading />
      ) : apps.isError ? (
        <LoadError what="your applications" onRetry={() => apps.refetch()} />
      ) : readyRows.length || appRows.length ? (
        <ul className={styles.list}>
          <li className={cx(styles.row, styles.listHead)} aria-hidden="true">
            <span className={styles.main}>Job</span>
            <span className={styles.status}>Status</span>
            <span className={styles.date}>Date</span>
            <span className={styles.confirm}>Submission</span>
            <span className={styles.actions} />
          </li>
          {readyRows.map((job) => (
            <ReadyRow key={job.id} job={job} />
          ))}
          {appRows.map((app) => (
            <ApplicationRow key={app.id} app={app} />
          ))}
        </ul>
      ) : (
        <Empty>
          {filter === 'ready'
            ? 'Nothing is waiting for your approval. When the agent finishes filling a form, it shows up here.'
            : 'No applications with this status yet.'}
        </Empty>
      )}
    </Page>
  );
}

function ReadyRow({ job }: { job: Job }) {
  const { open } = useOverlays();
  return (
    <li className={cx(styles.row, styles.ready)}>
      <div className={styles.main}>
        <b>{job.company}</b>
        <span className={styles.sub}>
          {job.role} · {job.ats}
        </span>
      </div>
      <div className={styles.status}>
        <Chip tone="teal">Ready to submit</Chip>
      </div>
      <div className={styles.date}>
        {job.readyAt && (
          <>
            <span>Filled {formatDay(job.readyAt)}</span>
            <span className={styles.sub}>{formatTime(job.readyAt)}</span>
          </>
        )}
      </div>
      <div className={cx(styles.confirm, styles.pending)}>
        <Icon name="warn" size={16} />
        <span>
          <b>Not submitted yet</b>
          <span className={styles.sub}>Waiting for your approval</span>
        </span>
      </div>
      <div className={styles.actions}>
        <Button variant="primary" size="sm" onClick={() => open({ type: 'review', jobId: job.id })}>
          Review and submit
        </Button>
      </div>
    </li>
  );
}

function ApplicationRow({ app }: { app: Application }) {
  const { open } = useOverlays();
  const { change, pending } = useStatusChange();
  const selectId = `status-${app.id}`;

  return (
    <li className={styles.row}>
      <div className={styles.main}>
        <b>
          {app.company}
          {app.isNew && <Chip tone="teal">New</Chip>}
        </b>
        <span className={styles.sub}>
          {app.role} · {app.ats}
        </span>
      </div>
      <div className={styles.status}>
        <label className="sr-only" htmlFor={selectId}>
          Status for {app.company}
        </label>
        <select
          id={selectId}
          value={app.status}
          disabled={pending}
          onChange={(e) => change(app, e.target.value as ApplicationStatus)}
        >
          {APPLICATION_STATUSES.map((status) => (
            <option key={status} value={status}>
              {APPLICATION_STATUS_LABELS[status]}
            </option>
          ))}
        </select>
      </div>
      <div className={styles.date}>
        <span>Sent {formatDay(app.submittedAt)}</span>
        <span className={styles.sub}>{daysAgo(app.submittedAt)}</span>
      </div>
      <div className={cx(styles.confirm, styles.ok)}>
        <Icon name="check" size={16} stroke={2.6} />
        {app.confirmation ? (
          <span>
            <b>Submission confirmed</b>
            <span className={styles.sub}>
              Ref {app.confirmation.reference} · {formatDateTime(app.confirmation.confirmedAt)}
            </span>
          </span>
        ) : app.submittedBy === 'you' ? (
          <span>
            <b>You submitted it</b>
            <span className={styles.sub}>On {app.company}’s site</span>
          </span>
        ) : (
          <span>
            <b>Sent</b>
            <span className={styles.sub}>No confirmation page seen</span>
          </span>
        )}
      </div>
      <div className={styles.actions}>
        {app.submittedBy === 'agent' && (
          <Button size="xs" onClick={() => open({ type: 'screenshot', applicationId: app.id })}>
            View screenshot
          </Button>
        )}
        <LinkButton small onClick={() => open({ type: 'application', applicationId: app.id })}>
          Details
        </LinkButton>
      </div>
    </li>
  );
}
