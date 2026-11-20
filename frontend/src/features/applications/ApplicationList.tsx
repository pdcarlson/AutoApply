/** The Applications list: jobs ready to submit, then submitted applications. */
import type { Application, ApplicationStatus, Job } from '@/api/types';
import { useOverlays } from '@/app/providers/overlays';
import { Chip } from '@/components/ui/Badges';
import { Button, LinkButton } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { APPLICATION_STATUSES, APPLICATION_STATUS_LABELS } from '@/lib/jobStatus';
import { daysAgo, formatDateTime, formatDay, formatTime } from '@/lib/format';
import { cx } from '@/lib/cx';
import { useStatusChange } from './useStatusChange';
import styles from './ApplicationList.module.css';

interface ApplicationListProps {
  readyJobs: Job[];
  applications: Application[];
}

/** A header row, then one row per ready job and per submitted application. */
export function ApplicationList({ readyJobs, applications }: ApplicationListProps) {
  return (
    <ul className={styles.list}>
      <li className={cx(styles.row, styles.listHead)} aria-hidden="true">
        <span className={styles.main}>Job</span>
        <span className={styles.status}>Status</span>
        <span className={styles.date}>Date</span>
        <span className={styles.confirm}>Submission</span>
        <span className={styles.actions} />
      </li>
      {readyJobs.map((job) => (
        <ReadyRow key={job.id} job={job} />
      ))}
      {applications.map((application) => (
        <ApplicationRow key={application.id} application={application} />
      ))}
    </ul>
  );
}

interface ReadyRowProps {
  job: Job;
}

function ReadyRow({ job }: ReadyRowProps) {
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

interface ApplicationRowProps {
  application: Application;
}

function ApplicationRow({ application }: ApplicationRowProps) {
  const { open } = useOverlays();
  const { change, pending } = useStatusChange();
  const selectId = `status-${application.id}`;
  const confirmation = application.confirmation
    ? {
        title: 'Submission confirmed',
        detail: `Ref ${application.confirmation.reference} · ${formatDateTime(application.confirmation.confirmedAt)}`,
      }
    : application.submittedBy === 'you'
      ? { title: 'You submitted it', detail: `On ${application.company}’s site` }
      : { title: 'Sent', detail: 'No confirmation page seen' };

  return (
    <li className={styles.row}>
      <div className={styles.main}>
        <b>
          {application.company}
          {application.isNew && <Chip tone="teal">New</Chip>}
        </b>
        <span className={styles.sub}>
          {application.role} · {application.ats}
        </span>
      </div>
      <div className={styles.status}>
        <label className="sr-only" htmlFor={selectId}>
          Status for {application.company}
        </label>
        <select
          id={selectId}
          value={application.status}
          disabled={pending}
          onChange={(event) => change(application, event.target.value as ApplicationStatus)}
        >
          {APPLICATION_STATUSES.map((status) => (
            <option key={status} value={status}>
              {APPLICATION_STATUS_LABELS[status]}
            </option>
          ))}
        </select>
      </div>
      <div className={styles.date}>
        <span>Sent {formatDay(application.submittedAt)}</span>
        <span className={styles.sub}>{daysAgo(application.submittedAt)}</span>
      </div>
      <div className={cx(styles.confirm, styles.ok)}>
        <Icon name="check" size={16} stroke={2.6} />
        <span>
          <b>{confirmation.title}</b>
          <span className={styles.sub}>{confirmation.detail}</span>
        </span>
      </div>
      <div className={styles.actions}>
        {application.submittedBy === 'agent' && (
          <Button
            size="xs"
            onClick={() => open({ type: 'screenshot', applicationId: application.id })}
          >
            View screenshot
          </Button>
        )}
        <LinkButton
          small
          onClick={() => open({ type: 'application', applicationId: application.id })}
        >
          Details
        </LinkButton>
      </div>
    </li>
  );
}
