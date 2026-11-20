/** A question the agent paused on, with the right way to answer it. */
import { useState } from 'react';
import type { AgentQuestion, AnswerScope, Job } from '@/api/types';
import { useAgentSettings, usePickAnswer } from '@/api/queries';
import { DraftPreview } from './DraftPreview';
import { OptionPicker } from './OptionPicker';
import { ProposedAnswer } from './ProposedAnswer';
import { QuestionThread } from './QuestionThread';
import { ReplyBox } from './ReplyBox';
import styles from './QuestionPanel.module.css';

interface QuestionPanelProps {
  job: Job;
  question: AgentQuestion;
}

/**
 * When the form's field takes one of a fixed set of options, the user picks one. Otherwise the
 * user replies in plain words, and the backend turns the reply into the form's answer and shows
 * it here before anything is entered.
 */
export function QuestionPanel({ job, question }: QuestionPanelProps) {
  const threshold = useAgentSettings().data?.confidenceThreshold;
  const pick = usePickAnswer();
  // Kept here so the choice survives "Change my reply" and a new proposal.
  const [scope, setScope] = useState<AnswerScope>(question.defaultScope);
  const { draft, proposedAnswer: proposed, pickOptions } = question;
  const draftShown = question.type === 'draft' && !proposed ? draft : null;

  const answerArea = proposed ? (
    <ProposedAnswer
      job={job}
      proposed={proposed}
      threshold={threshold}
      scope={scope}
      onScopeChange={setScope}
    />
  ) : pickOptions?.length ? (
    <OptionPicker
      options={pickOptions}
      disabled={pick.isPending}
      onPick={(value) => pick.mutate({ jobId: job.id, value })}
      isError={pick.isError}
    />
  ) : (
    <ReplyBox jobId={job.id} placeholder={question.placeholder} />
  );

  return (
    <div className={styles.ask}>
      <span className="eyebrow">{job.company}’s form asks</span>
      <p className={styles.askQuestion}>{question.field}</p>
      {draftShown && (
        <DraftPreview draft={draftShown} confidence={question.confidence} threshold={threshold} />
      )}
      <QuestionThread messages={question.messages} />
      {answerArea}
    </div>
  );
}
