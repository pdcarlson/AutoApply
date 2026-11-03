import { useEffect, useRef, useState } from 'react';
import type { AddJobConflict, Job } from '@/api/types';
import { isApiError } from '@/api/client';
import { useAddJob } from '@/api/queries';
import { Button } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { Spinner } from '@/components/ui/Spinner';
import { checkJobLink, SUPPORTED_HINT } from '@/lib/jobLinks';
import { formatDay } from '@/lib/format';
import { cx } from '@/lib/cx';
import styles from './PasteLink.module.css';

type Message =
  | { kind: 'busy'; text: string }
  | { kind: 'error' | 'info'; title: string; text: string; hint?: string; jobId?: string };

/** Turns an add-job failure from the backend into what to tell the user. */
function messageForError(error: unknown): Message {
  if (isApiError(error)) {
    const conflict = error.details as Partial<AddJobConflict>;
    switch (error.code) {
      case 'already_applied':
        return {
          kind: 'info',
          title: 'Already sent',
          text: `You applied to ${conflict.company ?? 'this company'}${conflict.sentAt ? ` on ${formatDay(conflict.sentAt)}` : ''}. Each job is sent once.`,
        };
      case 'already_in_inbox':
        return {
          kind: 'info',
          title: 'Already in your Inbox',
          text: [conflict.company, conflict.role].filter(Boolean).join(' · '),
          jobId: conflict.jobId,
        };
      case 'posting_closed':
        return {
          kind: 'error',
          title: 'This posting is closed',
          text: 'The company isn’t taking applications for it anymore, so there’s nothing to add.',
        };
      case 'unsupported_site':
        return {
          kind: 'error',
          title: 'This site isn’t supported',
          text: error.message,
          hint: SUPPORTED_HINT,
        };
      case 'invalid_url':
        return { kind: 'error', title: 'That doesn’t look like a link', text: error.message };
    }
  }
  return {
    kind: 'error',
    title: 'We couldn’t read that posting',
    text: 'Something went wrong on our side. Try again in a moment.',
  };
}

interface PasteLinkProps {
  onAdded: (job: Job) => void;
  onShowJob: (jobId: string) => void;
}

/** "Apply from a job link": paste a Greenhouse or Ashby URL and add it to the Inbox. */
export function PasteLink({ onAdded, onShowJob }: PasteLinkProps) {
  const [value, setValue] = useState('');
  const [message, setMessage] = useState<Message | null>(null);
  const addJob = useAddJob();
  const ref = useRef<HTMLDivElement>(null);

  // Clicking elsewhere dismisses a result message (not the in-progress one).
  useEffect(() => {
    if (!message || message.kind === 'busy') return;
    const onDown = (event: MouseEvent) => {
      if (!ref.current?.contains(event.target as Node)) setMessage(null);
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [message]);

  const submit = () => {
    if (!value.trim() || addJob.isPending) return;
    const check = checkJobLink(value);
    if (!check.ok) {
      setMessage({ kind: 'error', title: check.title, text: check.text, hint: check.hint });
      return;
    }
    setMessage({ kind: 'busy', text: `Reading the posting from ${check.ats}…` });
    addJob.mutate(check.url, {
      onSuccess: (job) => {
        setValue('');
        setMessage(null);
        onAdded(job);
      },
      onError: (error) => setMessage(messageForError(error)),
    });
  };

  return (
    <section className={styles.hero} aria-labelledby="paste-title">
      <h2 className={cx('h3', styles.title)} id="paste-title">
        Apply from a job link
      </h2>
      <div className={styles.paste} ref={ref}>
        <div className={styles.row}>
          <label className={styles.field} htmlFor="paste-link">
            <Icon name="link" size={16} stroke={1.75} />
            <span className="sr-only">Add a job by pasting its link</span>
            <input
              id="paste-link"
              type="url"
              inputMode="url"
              autoComplete="off"
              spellCheck={false}
              placeholder="https://boards.greenhouse.io/company/jobs/…"
              value={value}
              onChange={(e) => {
                setValue(e.target.value);
                if (message?.kind !== 'busy') setMessage(null);
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  submit();
                }
              }}
            />
          </label>
          <Button
            variant="primary"
            className={styles.button}
            disabled={!value.trim()}
            loading={addJob.isPending}
            loadingLabel="Adding…"
            onClick={submit}
          >
            Add job
          </Button>
        </div>
        {message && <Popover message={message} onShowJob={onShowJob} />}
      </div>
    </section>
  );
}

function Popover({ message, onShowJob }: { message: Message; onShowJob: (jobId: string) => void }) {
  if (message.kind === 'busy') {
    return (
      <div className={cx(styles.pop, styles.busy)} role="status">
        <Spinner />
        <span>{message.text}</span>
      </div>
    );
  }
  return (
    <div
      className={cx(styles.pop, message.kind === 'error' && styles.error)}
      role={message.kind === 'error' ? 'alert' : 'status'}
    >
      <span className={styles.popTitle}>{message.title}</span>
      <span className="ink2">{message.text}</span>
      {message.hint && <span className="tiny muted">{message.hint}</span>}
      {message.jobId && (
        <div>
          <Button size="xs" onClick={() => onShowJob(message.jobId!)}>
            Show it in my Inbox
          </Button>
        </div>
      )}
    </div>
  );
}
