import { useId, useState } from 'react';
import type { Application, Job } from '@/api/types';
import { useEnterCode } from '@/api/queries';
import { Button } from '@/components/ui/Button';
import { ErrorBox } from '@/components/ui/Callouts';
import styles from './panels.module.css';

interface VerificationCodeFormProps {
  job: Pick<Job, 'id' | 'ats'>;
  onSubmitted: (app: Application) => void;
}

/**
 * The site emailed the user a code after Submit (`job.asksForCode`). The user types it here and
 * the agent enters it into the form that is still open, then submits. A wrong code can be
 * retried: the form keeps asking.
 */
export function VerificationCodeForm({ job, onSubmitted }: VerificationCodeFormProps) {
  const inputId = useId();
  const [code, setCode] = useState('');
  const enterCode = useEnterCode();
  const trimmed = code.replace(/\s+/g, '');

  return (
    <form
      className={styles.codeForm}
      onSubmit={(event) => {
        event.preventDefault();
        if (!trimmed || enterCode.isPending) return;
        enterCode.mutate({ jobId: job.id, code: trimmed }, { onSuccess: onSubmitted });
      }}
    >
      <label htmlFor={inputId} className="small ink2">
        Check your email for a message from {job.ats} (it can take a minute, and may be in spam).
        Enter the code below and the agent types it into the form and submits it.
      </label>
      <div className={styles.codeRow}>
        <input
          id={inputId}
          className={styles.codeInput}
          value={code}
          onChange={(event) => setCode(event.target.value)}
          placeholder="Verification code"
          autoComplete="one-time-code"
          autoCapitalize="off"
          autoCorrect="off"
          spellCheck={false}
          maxLength={32}
          disabled={enterCode.isPending}
        />
        <Button
          type="submit"
          variant="primary"
          size="sm"
          disabled={!trimmed}
          loading={enterCode.isPending}
          loadingLabel="Submitting…"
        >
          Submit code
        </Button>
      </div>
      {enterCode.isError && <ErrorBox>{enterCode.error.message}</ErrorBox>}
    </form>
  );
}
