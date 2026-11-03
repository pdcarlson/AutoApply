import { Link } from 'react-router';
import { paths } from '@/app/paths';
import { buttonClass } from '@/components/ui/classNames';
import { Brand } from '@/components/ui/DataDisplay';
import { Icon } from '@/components/ui/Icon';
import styles from './auth.module.css';

const REMOVED = [
  'Profile and resume file',
  'Answer bank',
  'Applications and what was sent',
  'Screenshots of submitted forms',
  'Job preferences and agent controls',
];

export function AccountDeletedPage() {
  return (
    <div className={styles.frame}>
      <header className={styles.top}>
        <Brand />
      </header>
      <main id="main" className={styles.centered}>
        <div className={styles.centeredCard}>
          <span className="eyebrow">Account deleted</span>
          <h1 className="h1">Everything is gone</h1>
          <p className="ink2">
            We removed your profile, resume file, saved answers, applications, submission records,
            and screenshots. Nothing tied to your account is left on our servers.
          </p>
          <ul className={styles.promises}>
            {REMOVED.map((item) => (
              <li key={item}>
                <Icon name="check" size={16} stroke={2.5} />
                {item}
              </li>
            ))}
          </ul>
          <div>
            <Link className={buttonClass()} to={paths.signIn}>
              Back to sign in
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}
