/** Live progress while the backend reads an uploaded resume. */
import type { ResumeParse } from '@/api/types';
import { Icon } from '@/components/ui/Icon';
import { Spinner } from '@/components/ui/Spinner';
import { cx } from '@/lib/cx';
import styles from './ResumeParseProgress.module.css';

interface ResumeParseProgressProps {
  parse: ResumeParse;
}

/** Shows which resume sections have been read so far. */
export function ResumeParseProgress({ parse }: ResumeParseProgressProps) {
  const isParsing = parse.status === 'parsing';
  const title = isParsing ? `Reading ${parse.file.name}…` : `Read ${parse.file.name}`;
  const subtitle = isParsing ? 'Usually under 15 seconds' : 'Done. Check it on the next step.';
  return (
    <div className={styles.parse} aria-live="polite">
      <div className={styles.parseHead}>
        {isParsing ? <Spinner /> : <Icon name="check" size={18} stroke={2.5} />}
        <span className={styles.parseHeadText}>
          <b className="small">{title}</b>
          <span className="tiny muted">{subtitle}</span>
        </span>
      </div>
      <ul className={styles.parseList}>
        {parse.sections.map((section) => {
          const isWarning = section.status === 'warn';
          return (
            <li key={section.label} className={cx(isWarning && styles.warn)}>
              <Icon name={isWarning ? 'warn' : 'check'} size={16} stroke={isWarning ? 2 : 2.5} />
              {section.label}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
