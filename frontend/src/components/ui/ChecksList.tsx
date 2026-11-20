/** A list of how a posting compares with the user's profile. */
import type { ProfileCheck } from '@/api/types';
import { cx } from '@/lib/cx';
import { Icon } from './Icon';
import styles from './ChecksList.module.css';

const CHECK_ICONS = { ok: 'check', warn: 'warn', bad: 'bad' } as const;

interface ChecksListProps {
  checks: ProfileCheck[];
  /** Bigger text and icons. */
  large?: boolean;
}

/** How a posting compares with the profile: met, partly met, or not met. */
export function ChecksList({ checks, large }: ChecksListProps) {
  return (
    <ul className={cx(styles.checks, large && styles.checksLarge)}>
      {checks.map((check) => (
        <li key={check.text}>
          <Icon
            name={CHECK_ICONS[check.status]}
            size={large ? 20 : 18}
            stroke={check.status === 'ok' ? 2.5 : 2}
            className={styles[`check-${check.status}`]}
          />
          <span>{check.text}</span>
        </li>
      ))}
    </ul>
  );
}
