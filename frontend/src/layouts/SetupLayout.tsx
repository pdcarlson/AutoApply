import type { ReactNode } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router';
import { useSignOut } from '@/api/queries';
import { paths } from '@/app/paths';
import { Button, LinkButton } from '@/components/ui/Button';
import { Brand } from '@/components/ui/DataDisplay';
import { Icon } from '@/components/ui/Icon';
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
          <span style={{ width: `${Math.round((100 * (current + 1)) / STEPS.length)}%` }} />
        </span>
        <LinkButton
          small
          className={styles.exit}
          onClick={() => signOut.mutate(undefined, { onSettled: () => navigate(paths.signIn) })}
        >
          Sign out
        </LinkButton>
      </header>
      <main id="main" className={styles.main}>
        <Outlet />
      </main>
    </div>
  );
}

interface SetupFooterProps {
  onBack?: () => void;
  onNext: () => void;
  nextLabel: string;
  nextDisabled?: boolean;
  loading?: boolean;
  /** Why Next is disabled, shown beside it. */
  note?: string | null;
}

/** Back / Continue row under a setup step's content. */
export function SetupFooter({
  onBack,
  onNext,
  nextLabel,
  nextDisabled,
  loading,
  note,
}: SetupFooterProps) {
  return (
    <footer className={styles.foot}>
      {onBack && (
        <Button variant="ghost" onClick={onBack}>
          Back
        </Button>
      )}
      <div className={styles.footRight}>
        {note && <span className={cx('small muted', styles.footNote)}>{note}</span>}
        <Button variant="primary" disabled={nextDisabled} loading={loading} onClick={onNext}>
          {nextLabel}
          <Icon name="right" size={16} stroke={2} />
        </Button>
      </div>
    </footer>
  );
}

/** Title and lead paragraph at the top of a setup step. */
export function SetupIntro({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className={styles.intro}>
      <h1 className="h1">{title}</h1>
      <p className="lede">{children}</p>
    </div>
  );
}
