import { useId, useState } from 'react';
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

/** Option lists longer than this get a filter box above the buttons. */
const BUTTONS_WITHOUT_FILTER = 12;
/** How many matching options a filtered list shows at once. */
const SHOWN_WHEN_FILTERED = 12;

/**
 * A question the agent paused on. When the form's field takes one of a fixed set of options,
 * the user picks one; there's nothing to type. Otherwise the user replies in plain words, and
 * the backend turns the reply into the form's answer and shows it here before anything is
 * entered.
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

      {!proposed && question.pickOptions?.length ? (
        <OptionPicker
          options={question.pickOptions}
          disabled={pick.isPending}
          onPick={(value) => pick.mutate({ jobId: job.id, value })}
          isError={pick.isError}
        />
      ) : !proposed ? (
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

/** The form's options as buttons. A long list gets a filter box that only narrows the list. */
function OptionPicker({
  options,
  disabled,
  onPick,
  isError,
}: {
  options: string[];
  disabled: boolean;
  onPick: (value: string) => void;
  isError: boolean;
}) {
  const [filter, setFilter] = useState('');
  const filterId = useId();
  const long = options.length > BUTTONS_WITHOUT_FILTER;
  const wanted = filter.trim().toLowerCase();
  const matches = wanted ? options.filter((o) => o.toLowerCase().includes(wanted)) : options;
  const shown = long ? matches.slice(0, SHOWN_WHEN_FILTERED) : matches;
  const hidden = matches.length - shown.length;

  return (
    <>
      {long && (
        <div className={styles.filter}>
          <label className="sr-only" htmlFor={filterId}>
            Filter options
          </label>
          <input
            id={filterId}
            type="search"
            placeholder={`Filter ${options.length} options…`}
            value={filter}
            autoComplete="off"
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>
      )}
      <div className={styles.row} role="group" aria-label="Options">
        {!long && <span className="small">Pick one:</span>}
        {shown.map((option) => (
          <Button key={option} size="sm" disabled={disabled} onClick={() => onPick(option)}>
            {option}
          </Button>
        ))}
        {shown.length === 0 && <span className="small muted">No option matches that.</span>}
      </div>
      {hidden > 0 && (
        <span className="tiny muted">
          {hidden} more {hidden === 1 ? 'option matches' : 'options match'}. Keep typing to narrow
          the list.
        </span>
      )}
      {isError && (
        <span className="tiny" role="alert">
          That didn’t go through. Try again.
        </span>
      )}
      <span className="tiny muted">
        This field only takes one of the form’s options. You’ll see your pick before it’s used.
      </span>
    </>
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
