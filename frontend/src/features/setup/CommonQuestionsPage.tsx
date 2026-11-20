/** The last setup step: common application questions answered once. */
import { useNavigate } from 'react-router';
import type { CommonAnswers } from '@/api/types';
import { useCommonAnswers } from '@/api/queries';
import { paths } from '@/app/paths';
import { ErrorBox } from '@/components/ui/Callouts';
import { Loading, LoadError } from '@/components/ui/LoadStates';
import { SetupFooter } from '@/layouts/SetupFooter';
import { SetupIntro } from '@/layouts/SetupIntro';
import { JobQuestions } from './JobQuestions';
import { SelfIdQuestions } from './SelfIdQuestions';
import { useCommonAnswersDraft } from './useCommonAnswersDraft';
import styles from './CommonQuestionsPage.module.css';

/** Loads the saved answers and shows the questions form. */
export function CommonQuestionsPage() {
  const answers = useCommonAnswers();
  if (answers.isPending) return <Loading />;
  if (answers.isError) return <LoadError what="your answers" onRetry={() => answers.refetch()} />;
  return <QuestionsForm initial={answers.data} />;
}

interface QuestionsFormProps {
  initial: CommonAnswers;
}

function QuestionsForm({ initial }: QuestionsFormProps) {
  const navigate = useNavigate();
  const { draft, patch, toggleSkip, finish, error, isFinishing } = useCommonAnswersDraft(initial);
  const skips = { skipped: draft.skipped, onToggleSkip: toggleSkip };

  // The error is shown from the mutation state, so the rejected promise needs no handler.
  const handleFinish = () => void finish().catch(() => undefined);

  return (
    <>
      <SetupIntro title="Answer these once">
        Your answers go into your Answer bank, and you can change them any time.
      </SetupIntro>
      <div className={styles.questionList}>
        <JobQuestions draft={draft} onChange={patch} skips={skips} />
        <SelfIdQuestions draft={draft} onChange={patch} skips={skips} />
      </div>
      {error && <ErrorBox>We couldn’t finish setup. {error.message}</ErrorBox>}
      <SetupFooter
        onBack={() => navigate(paths.setupProfile)}
        onNext={handleFinish}
        loading={isFinishing}
        nextLabel="Confirm profile and finish"
      />
    </>
  );
}
