/** The answer the agent will enter, waiting for the user to accept or change it. */
import type { AgentQuestion, AnswerScope, Job } from '@/api/types';
import { useAcceptAnswer, useReviseReply } from '@/api/queries';
import { useToast } from '@/app/providers/toast';
import { Button } from '@/components/ui/Button';
import { Choice } from '@/components/ui/Choice';
import { replyInputId } from './replyInputId';
import styles from './ProposedAnswer.module.css';

interface ProposedAnswerProps {
  job: Job;
  proposed: NonNullable<AgentQuestion['proposedAnswer']>;
  threshold: number | undefined;
  scope: AnswerScope;
  onScopeChange: (scope: AnswerScope) => void;
}

/** Shows the value and confidence, where to save it, and Use / Change buttons. */
export function ProposedAnswer({
  job,
  proposed,
  threshold,
  scope,
  onScopeChange,
}: ProposedAnswerProps) {
  const notify = useToast();
  const accept = useAcceptAnswer();
  const revise = useReviseReply();
  const scopeName = `scope-${replyInputId(job.id)}`;

  const acceptAnswer = () =>
    accept.mutate(
      { jobId: job.id, scope },
      {
        onSuccess: () => notify(`Saved to your Answer bank. ${job.company} is back in the queue.`),
      },
    );

  return (
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
          name={scopeName}
          checked={scope === 'all'}
          onChange={() => onScopeChange('all')}
        >
          Use for every company that asks
        </Choice>
        <Choice
          type="radio"
          name={scopeName}
          checked={scope === 'company'}
          onChange={() => onScopeChange('company')}
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
  );
}
