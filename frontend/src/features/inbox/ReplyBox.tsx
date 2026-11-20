/** The plain-words reply box under an agent question. */
import { useState, type KeyboardEvent } from 'react';
import { useReplyToQuestion } from '@/api/queries';
import { Button } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { replyInputId } from './replyInputId';
import styles from './ReplyBox.module.css';

interface ReplyBoxProps {
  jobId: string;
  placeholder: string;
}

/** Sends the reply on Send or Enter (Shift+Enter adds a line). */
export function ReplyBox({ jobId, placeholder }: ReplyBoxProps) {
  const [reply, setReply] = useState('');
  const send = useReplyToQuestion();
  const inputId = replyInputId(jobId);

  const submitReply = () => {
    const text = reply.trim();
    if (!text) return;
    send.mutate({ jobId, text }, { onSuccess: () => setReply('') });
  };

  const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      submitReply();
    }
  };

  return (
    <>
      <div className={styles.reply}>
        <label className="sr-only" htmlFor={inputId}>
          Your reply
        </label>
        <textarea
          id={inputId}
          rows={2}
          placeholder={placeholder}
          value={reply}
          onChange={(event) => setReply(event.target.value)}
          onKeyDown={handleKeyDown}
        />
        <Button
          variant="primary"
          size="sm"
          disabled={!reply.trim()}
          loading={send.isPending}
          onClick={submitReply}
        >
          <Icon name="send" size={16} />
          Send
        </Button>
      </div>
      {send.isError && (
        <span className="tiny" role="alert">
          That didn’t send. Try again.
        </span>
      )}
      <span className="tiny muted">
        Reply in plain words. The agent turns your reply into the form’s answer and shows it to you
        before using it.
      </span>
    </>
  );
}
