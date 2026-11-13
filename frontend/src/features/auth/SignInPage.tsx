import { useMutation } from '@tanstack/react-query';
import { useLocation } from 'react-router';
import { authApi } from '@/api/endpoints';
import { Button } from '@/components/ui/Button';
import { ErrorBox } from '@/components/ui/Callouts';
import { Brand } from '@/components/ui/DataDisplay';
import styles from './auth.module.css';

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
    'A Greenhouse, Lever or Ashby link. The agent fills the form, and you approve it before it’s submitted.',
  ],
] as const;

interface SignInState {
  from?: string;
  signInError?: 'cancelled' | 'failed';
}

export function SignInPage() {
  const state = (useLocation().state ?? {}) as SignInState;
  const start = useMutation({
    mutationFn: () => authApi.startGoogleSignIn(state.from ?? '/'),
    onSuccess: ({ authorizationUrl }) => window.location.assign(authorizationUrl),
  });
  // Stays "waiting" after success too, while the browser follows the returned URL.
  const waiting = start.isPending || start.isSuccess;

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
            loading={waiting}
            loadingLabel="Starting…"
            onClick={() => start.mutate()}
          >
            Begin Onboarding
          </Button>
          <p className={styles.finePrint}>
            By continuing you agree to the Terms and Privacy policy.
          </p>
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
