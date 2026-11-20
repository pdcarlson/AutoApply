/** The frame around the three setup steps. */
import { Outlet, useLocation, useNavigate } from 'react-router';
import { useSignOut } from '@/api/queries';
import { paths } from '@/app/paths';
import { Brand } from '@/components/ui/Brand';
import { LinkButton } from '@/components/ui/Button';
import { cx } from '@/lib/cx';
import styles from './SetupLayout.module.css';

const STEPS = [
  { path: paths.setupResume, label: 'Resume' },
  { path: paths.setupProfile, label: 'Check profile' },
  { path: paths.setupQuestions, label: 'Common questions' },
];

/** Frame for the three setup steps: header with progress, then the step's page. */
export function SetupLayout() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const signOut = useSignOut();
  const current = Math.max(
    0,
    STEPS.findIndex((step) => step.path === pathname),
  );
  const percentDone = Math.round((100 * (current + 1)) / STEPS.length);
  const handleSignOut = () =>
    signOut.mutate(undefined, { onSettled: () => navigate(paths.signIn) });

  return (
    <div className={styles.frame}>
      <header className={styles.top}>
        <Brand />
        <span className={styles.count}>
          Step {current + 1} of {STEPS.length}
          <span className={styles.compact}> · {STEPS[current].label}</span>
        </span>
        <ol className={styles.steps} aria-label="Setup steps">
          {STEPS.map((step, index) => (
            <li
              key={step.path}
              className={cx(index === current && styles.current)}
              aria-current={index === current ? 'step' : undefined}
            >
              {step.label}
            </li>
          ))}
        </ol>
        <span className={styles.bar} aria-hidden="true">
          <span style={{ width: `${percentDone}%` }} />
        </span>
        <LinkButton small className={styles.exit} onClick={handleSignOut}>
          Sign out
        </LinkButton>
      </header>
      <main id="main" className={styles.main}>
        <Outlet />
      </main>
    </div>
  );
}
