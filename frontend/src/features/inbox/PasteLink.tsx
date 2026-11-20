/** The Inbox's "Apply from a job link" box. */
import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import type { Job } from '@/api/types';
import { useAddJob } from '@/api/queries';
import { Button } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { checkJobLink } from '@/lib/jobLinks';
import { cx } from '@/lib/cx';
import { messageForError, type PasteLinkMessage } from './pasteLinkMessages';
import { PasteLinkPopover } from './PasteLinkPopover';
import styles from './PasteLink.module.css';

interface PasteLinkProps {
  onAdded: (job: Job) => void;
  onShowJob: (jobId: string) => void;
}

/** "Apply from a job link": paste a Greenhouse or Ashby URL and add it to the Inbox. */
export function PasteLink({ onAdded, onShowJob }: PasteLinkProps) {
  const [value, setValue] = useState('');
  const [message, setMessage] = useState<PasteLinkMessage | null>(null);
  const addJob = useAddJob();
  const pasteRef = useRef<HTMLDivElement>(null);

  // Clicking elsewhere dismisses a result message (not the in-progress one).
  useEffect(() => {
    if (!message || message.kind === 'busy') return;
    const handleMouseDown = (event: MouseEvent) => {
      if (!pasteRef.current?.contains(event.target as Node)) setMessage(null);
    };
    document.addEventListener('mousedown', handleMouseDown);
    return () => document.removeEventListener('mousedown', handleMouseDown);
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

  const handleChange = (next: string) => {
    setValue(next);
    if (message?.kind !== 'busy') setMessage(null);
  };

  const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      submit();
    }
  };

  return (
    <section className={styles.hero} aria-labelledby="paste-title">
      <h2 className={cx('h3', styles.title)} id="paste-title">
        Apply from a job link
      </h2>
      <div className={styles.paste} ref={pasteRef}>
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
              onChange={(event) => handleChange(event.target.value)}
              onKeyDown={handleKeyDown}
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
        {message && <PasteLinkPopover message={message} onShowJob={onShowJob} />}
      </div>
    </section>
  );
}
