/** The list of what happened to an application. */
import type { TimelineEvent } from '@/api/types';
import { cx } from '@/lib/cx';
import { daysAgo, formatDateTime } from '@/lib/format';
import styles from './Timeline.module.css';

/** "4 days" for the step happening now; a date and time for past steps. */
const eventWhen = (event: TimelineEvent) =>
  event.kind === 'current' ? daysAgo(event.at).replace(' ago', '') : formatDateTime(event.at);

interface TimelineProps {
  events: TimelineEvent[];
}

/** What happened to an application, oldest first. The `current` step shows elapsed time. */
export function Timeline({ events }: TimelineProps) {
  return (
    <ol className={styles.timeline}>
      {events.map((event, index) => (
        <li key={index} className={cx(event.kind === 'current' && styles.current)}>
          <span className={cx(styles.timelineDot, styles[`dot-${event.kind}`])} />
          <span>{event.text}</span>
          <span className={styles.timelineWhen}>{eventWhen(event)}</span>
        </li>
      ))}
    </ol>
  );
}
