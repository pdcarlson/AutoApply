/** The side drawer with everything about one sent application. */
import { useState } from 'react';
import { useApplication } from '@/api/queries';
import { useApiImage } from '@/api/useApiImage';
import { useOverlays } from '@/app/providers/overlays';
import { Chip } from '@/components/ui/Badges';
import { Button, LinkButton } from '@/components/ui/Button';
import { Note } from '@/components/ui/Callouts';
import { Drawer, DrawerSection } from '@/components/ui/Drawer';
import { FieldList } from '@/components/ui/FieldList';
import { Icon } from '@/components/ui/Icon';
import { Loading, LoadError } from '@/components/ui/LoadStates';
import { Timeline } from '@/components/ui/Timeline';
import {
  APPLICATION_STATUS_LABELS,
  NEXT_STATUS,
  applicationChip,
  isClosedStatus,
} from '@/lib/jobStatus';
import { formatDateTime } from '@/lib/format';
import { orderFields } from './orderFields';
import { useStatusChange } from './useStatusChange';
import styles from './ApplicationDrawer.module.css';

const COLLAPSED_FIELDS = 8;

interface ApplicationDrawerProps {
  applicationId: string;
}

/** Everything about one sent application: timeline, what was sent, and the screenshot. */
export function ApplicationDrawer({ applicationId }: ApplicationDrawerProps) {
  const { close, open } = useOverlays();
  const application = useApplication(applicationId);
  const { change, pending } = useStatusChange();
  const [isShowingAll, setIsShowingAll] = useState(false);
  const data = application.data;
  const screenshot = useApiImage(data?.screenshotUrl);

  if (!data) {
    return (
      <Drawer
        labelledBy="drawer-title"
        onClose={close}
        head={
          <h2 id="drawer-title" className="sr-only">
            Application
          </h2>
        }
      >
        {application.isError ? (
          <LoadError what="this application" onRetry={() => application.refetch()} />
        ) : (
          <Loading />
        )}
      </Drawer>
    );
  }

  const chip = applicationChip(data.status);
  const fields = orderFields(data.fields);
  const nextStatus = NEXT_STATUS[data.status];

  const head = (
    <>
      <div className={styles.drawerTop}>
        <Chip tone={chip.tone}>{chip.label}</Chip>
      </div>
      <h2 id="drawer-title" className={styles.drawerTitle}>
        {data.role}
      </h2>
      <div className={styles.drawerSub}>
        <span>
          {data.company} · {data.location}
        </span>
        <a href={data.url} target="_blank" rel="noopener noreferrer" className={styles.external}>
          Open posting
          <Icon name="external" size={14} />
        </a>
      </div>
    </>
  );

  const footer = (
    <>
      {nextStatus && (
        <Button variant="primary" grow disabled={pending} onClick={() => change(data, nextStatus)}>
          {nextStatus === 'submitted'
            ? 'Reopen as submitted'
            : `Mark as ${APPLICATION_STATUS_LABELS[nextStatus].toLowerCase()}`}
        </Button>
      )}
      {!isClosedStatus(data.status) && (
        <Button disabled={pending} onClick={() => change(data, 'rejected')}>
          Mark as rejected
        </Button>
      )}
    </>
  );

  return (
    <Drawer labelledBy="drawer-title" onClose={close} head={head} footer={footer}>
      {data.confirmation && (
        <Note tone="teal" title="Submission confirmed">
          The agent saw {data.company}’s confirmation page on{' '}
          {formatDateTime(data.confirmation.confirmedAt)}. Reference {data.confirmation.reference}.
        </Note>
      )}
      {data.submittedBy === 'you' && (
        <Note title="You finished this one">
          The agent stopped at a CAPTCHA. These are the answers it had filled before it handed the
          form to you.
        </Note>
      )}
      <DrawerSection title="Timeline">
        <Timeline events={data.timeline} />
      </DrawerSection>
      <DrawerSection
        title="What was sent"
        aside="Every value scored at or above your threshold when it was filled"
      >
        <FieldList fields={isShowingAll ? fields : fields.slice(0, COLLAPSED_FIELDS)} />
        {fields.length > COLLAPSED_FIELDS && (
          <LinkButton
            small
            className={styles.showMore}
            onClick={() => setIsShowingAll(!isShowingAll)}
          >
            {isShowingAll ? 'Show fewer fields' : `Show all ${fields.length} fields`}
          </LinkButton>
        )}
      </DrawerSection>
      {data.screenshotUrl && (
        <DrawerSection
          title="Screenshot of the submitted application"
          aside="Saved when it was submitted"
        >
          <button
            type="button"
            className={styles.thumbnail}
            aria-label="Enlarge the screenshot"
            onClick={() => open({ type: 'screenshot', applicationId: data.id })}
          >
            <img src={screenshot} alt="" />
          </button>
        </DrawerSection>
      )}
    </Drawer>
  );
}
