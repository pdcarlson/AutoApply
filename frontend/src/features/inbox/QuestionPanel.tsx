import { useState } from 'react';
import type { AgentQuestion, AnswerScope, Job } from '@/api/types';
import {
  useAcceptAnswer,
  useAgentSettings,
  usePickAnswer,
  useReplyToQuestion,
  useReviseReply,
} from '@/api/queries';
import { useToast } from '@/app/providers/toast';
import { Button } from '@/components/ui/Button';
import { Choice } from '@/components/ui/Form';
import { Icon } from '@/components/ui/Icon';
import styles from './panels.module.css';

/**
 * A question the agent paused on. The user replies in plain words; the backend turns the
 * reply into the form's answer and shows it here before anything is entered.
 */
export function QuestionPanel({ job, question }: { job: Job; question: AgentQuestion }) {
  const notify = useToast();
  const threshold = useAgentSettings().data?.confidenceThreshold;
  const [reply, setReply] = useState('');
  const [scope, setScope] = useState<AnswerScope>(question.defaultScope);
  const send = useReplyToQuestion();
  const pick = usePickAnswer();
  const revise = useReviseReply();
  const accept = useAcceptAnswer();
  const replyId = `reply-${job.id}`;

  const submitReply = () => {
    const text = reply.trim();
    if (!text) return;
    send.mutate({ jobId: job.id, text }, { onSuccess: () => setReply('') });
  };

  const acceptAnswer = () =>
    accept.mutate(
      { jobId: job.id, scope },
      {
        onSuccess: () => notify(`Saved to your Answer bank. ${job.company} is back in the queue.`),
      },
    );

  const proposed = question.proposedAnswer;

  return (
    <div className={styles.ask}>
      <span className="eyebrow">{job.company}’s form asks</span>
      <p className={styles.askQuestion}>{question.field}</p>

      {question.type === 'draft' && question.draft && !proposed && (
        <DraftPreview
          draft={question.draft}
          confidence={question.confidence}
          threshold={threshold}
        />
      )}

      <div className={styles.thread}>
        {question.messages.map((message, index) =>
          message.from === 'you' ? (
            <div key={index} className={styles.messageYou}>
              {message.text}
            </div>
          ) : (
            <div key={index} className={styles.messageAgent}>
              <span className={styles.avatar} aria-hidden="true">
                AA
              </span>
              <p>{message.text}</p>
            </div>
          ),
        )}
      </div>

      {!proposed ? (
        <>
          <div className={styles.reply}>
            <label className="sr-only" htmlFor={replyId}>
              Your reply
            </label>
            <textarea
              id={replyId}
              rows={2}
              placeholder={question.placeholder}
              value={reply}
              onChange={(e) => setReply(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  submitReply();
                }
              }}
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
          {question.pickOptions && (
            <div className={styles.row}>
              <span className="small">Or pick it yourself:</span>
              {question.pickOptions.map((option) => (
                <Button
                  key={option}
                  size="sm"
                  disabled={pick.isPending}
                  onClick={() => pick.mutate({ jobId: job.id, value: option })}
                >
                  {option}
                </Button>
              ))}
            </div>
          )}
          {send.isError && (
            <span className="tiny" role="alert">
              That didn’t send. Try again.
            </span>
          )}
          <span className="tiny muted">
            Reply in plain words. The agent turns your reply into the form’s answer and shows it to
            you before using it.
          </span>
        </>
      ) : (
        <div className={styles.result}>
          <span className="eyebrow">I’ll enter</span>
          <p className={styles.resultValue}>{proposed.value}</p>
          <span className="tiny muted">
            Confidence {proposed.confidence}
            {threshold !== undefined && `, at or above your threshold of ${threshold}`}
          </span>
          <div className={styles.scope} role="radiogroup" aria-label="Save this answer for">
            <Choice
              type="radio"
              name={`scope-${replyId}`}
              checked={scope === 'all'}
              onChange={() => setScope('all')}
            >
              Use for every company that asks
            </Choice>
            <Choice
              type="radio"
              name={`scope-${replyId}`}
              checked={scope === 'company'}
              onChange={() => setScope('company')}
            >
              Only {job.company}
            </Choice>
          </div>
          <div className={styles.row}>
            <Button variant="primary" size="sm" loading={accept.isPending} onClick={acceptAnswer}>
              Use this answer
            </Button>
            <Button size="sm" disabled={revise.isPending} onClick={() => revise.mutate(job.id)}>
              Change my reply
            </Button>
          </div>
          <span className="tiny muted">
            It’s saved to your Answer bank, so no form asks you this twice.
          </span>
        </div>
      )}
    </div>
  );
}

function DraftPreview({
  draft,
  confidence,
  threshold,
}: {
  draft: { text: string; gap: string };
  confidence: number;
  threshold: number | undefined;
}) {
  const [before, after = ''] = draft.text.split(draft.gap);
  return (
    <div className={styles.draft}>
      <span className="eyebrow">Draft, from your profile only</span>
      <p>
        {before}
        <mark className={styles.gap}>{draft.gap}</mark>
        {after}
      </p>
      <span className="tiny muted">
        Confidence {confidence}
        {threshold !== undefined && `, below your threshold of ${threshold}`}. It has a gap, so it
        can’t be sent yet.
      </span>
    </div>
  );
}
