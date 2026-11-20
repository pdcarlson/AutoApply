/** The sign-in screen, with what happens after signing in. */
import { useMutation } from '@tanstack/react-query';
import { useLocation } from 'react-router';
import { useAuthActions } from '@/auth/actions';
import { Button } from '@/components/ui/Button';
import { ErrorBox } from '@/components/ui/Callouts';
import { Brand } from '@/components/ui/Brand';
import styles from './SignInPage.module.css';

const NEXT_STEPS = [
  [
    'Upload your resume',
    'PDF or DOCX, up to 5 MB. We pull out contact info, education, experience, and skills.',
  ],
  [
    'Check what we pulled',
    'Fix anything that’s wrong. Nothing goes into an application until you confirm it.',
  ],
  [
    'Answer the common questions',
    'Work authorization, sponsorship, dates, places, pay. Every one can be skipped.',
  ],
  [
    'Paste your first job',
    'A Greenhouse or Ashby link. The agent fills the form, and you approve it before it’s submitted.',
  ],
] as const;

/** What other screens pass along when they send the user here. */
interface SignInState {
  from?: string;
  signInError?: 'cancelled' | 'failed';
}

/** Starts sign-in, shows why the last attempt failed, and lists the setup steps. */
export function SignInPage() {
  const state = (useLocation().state ?? {}) as SignInState;
  const auth = useAuthActions();
  const start = useMutation({ mutationFn: () => auth.startSignIn(state.from ?? '/') });
  // Stays "waiting" after success too, while the browser follows the returned URL.
  const isWaiting = start.isPending || start.isSuccess;

  return (
    <div className={styles.welcome}>
      <main id="main" className={styles.welcomeMain}>
        <div className={styles.welcomeCard}>
          <Brand large />
          <div className={styles.stack}>
            <h1 className="h1">Sign in to Auto Apply</h1>
            <p className={styles.lead}>
              Paste a job link. The agent fills out the application, asks you before it guesses, and
              waits for your approval before it submits.
            </p>
          </div>
          {state.signInError === 'cancelled' && (
            <ErrorBox>
              <span>
                <b>Sign-in was cancelled.</b> Nothing was saved. Try again when you’re ready.
              </span>
            </ErrorBox>
          )}
          {(state.signInError === 'failed' || start.isError) && (
            <ErrorBox>
              <span>
                <b>We couldn’t sign you in.</b> Something went wrong on our side. Try again in a
                moment.
              </span>
            </ErrorBox>
          )}
          <Button
            className={styles.startBtn}
            loading={isWaiting}
            loadingLabel="Starting…"
            onClick={() => start.mutate()}
          >
            {auth.google ? 'Continue with Google' : 'Begin Onboarding'}
          </Button>
        </div>
      </main>
      <aside className={styles.nextSteps} aria-label="What happens next">
        <span className="eyebrow">What happens next</span>
        <ol className={styles.nextStepsList}>
          {NEXT_STEPS.map(([title, text], index) => (
            <li key={title}>
              <span className={styles.stepNumber}>{index + 1}</span>
              <div>
                <b>{title}</b>
                <span>{text}</span>
              </div>
            </li>
          ))}
        </ol>
      </aside>
    </div>
  );
}
