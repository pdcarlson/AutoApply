import { useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router';
import type { CommonAnswers, CommonQuestionKey } from '@/api/types';
import { useCommonAnswers, useConfirmProfile, useUpdateCommonAnswers } from '@/api/queries';
import { paths } from '@/app/paths';
import { useToast } from '@/app/providers/toast';
import { LinkButton } from '@/components/ui/Button';
import { ErrorBox } from '@/components/ui/Callouts';
import { Loading, LoadError } from '@/components/ui/DataDisplay';
import { Choice, DateInput, PillInput, Segmented } from '@/components/ui/Form';
import { inputClass } from '@/components/ui/classNames';
import { SetupFooter, SetupIntro } from '@/layouts/SetupLayout';
import { graduationOptions } from '@/lib/format';
import { cx } from '@/lib/cx';
import styles from './setup.module.css';

export function CommonQuestionsPage() {
  const answers = useCommonAnswers();
  if (answers.isPending) return <Loading />;
  if (answers.isError) return <LoadError what="your answers" onRetry={() => answers.refetch()} />;
  return <QuestionsForm initial={answers.data} />;
}

function QuestionsForm({ initial }: { initial: CommonAnswers }) {
  const navigate = useNavigate();
  const notify = useToast();
  const save = useUpdateCommonAnswers();
  const confirm = useConfirmProfile();
  const [draft, setDraft] = useState(initial);
  const patch = (changes: Partial<CommonAnswers>) => setDraft((d) => ({ ...d, ...changes }));

  const toggleSkip = (key: CommonQuestionKey) =>
    patch({
      skipped: draft.skipped.includes(key)
        ? draft.skipped.filter((k) => k !== key)
        : [...draft.skipped, key],
    });

  const finish = async () => {
    await save.mutateAsync(draft);
    await confirm.mutateAsync();
    navigate(paths.inbox);
    notify('Profile confirmed. Paste a job link to start your first application.');
  };

  const question = (key: CommonQuestionKey, label: string, control: ReactNode, hint?: string) => (
    <Question
      id={key}
      label={label}
      hint={hint}
      skipped={draft.skipped.includes(key)}
      onToggleSkip={() => toggleSkip(key)}
    >
      {control}
    </Question>
  );

  const error = save.error ?? confirm.error;

  return (
    <>
      <SetupIntro title="Answer these once">
        Your answers go into your Answer bank, and you can change them any time.
      </SetupIntro>
      <div className={styles.questionList}>
        {question(
          'workAuthorized',
          'Are you legally authorized to work in the United States?',
          <Segmented
            labelledBy="q-workAuthorized"
            options={['Yes', 'No']}
            value={draft.workAuthorized}
            onChange={(workAuthorized) => patch({ workAuthorized })}
          />,
        )}
        {question(
          'needsSponsorship',
          'Will you now or in the future need visa sponsorship?',
          <Segmented
            labelledBy="q-needsSponsorship"
            options={['Yes', 'No']}
            value={draft.needsSponsorship}
            onChange={(needsSponsorship) => patch({ needsSponsorship })}
          />,
        )}
        {question(
          'graduation',
          'When do you graduate?',
          <select
            className={inputClass(true)}
            aria-labelledby="q-graduation"
            value={draft.graduation ?? ''}
            onChange={(e) => patch({ graduation: e.target.value || null })}
          >
            <option value="">Choose a month</option>
            {withCurrent(graduationOptions(), draft.graduation).map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>,
        )}
        {question(
          'earliestStart',
          'Earliest start date',
          <DateInput
            labelledBy="q-earliestStart"
            value={draft.earliestStart ?? ''}
            onChange={(value) => patch({ earliestStart: value || null })}
          />,
        )}
        {question(
          'relocate',
          'Willing to relocate?',
          <Segmented
            labelledBy="q-relocate"
            options={['Yes', 'No', 'Depends']}
            value={draft.relocate}
            onChange={(relocate) => patch({ relocate })}
          />,
        )}
        {question(
          'locations',
          'Where do you want to work?',
          <PillInput
            items={draft.locations}
            onChange={(locations) => patch({ locations })}
            label="Places"
            addLabel="Add place"
            placeholder="City, State or Remote"
          />,
        )}
        {question(
          'expectedPay',
          'Expected pay (per year)',
          <input
            className={inputClass(true)}
            inputMode="numeric"
            aria-labelledby="q-expectedPay"
            placeholder="e.g. 85,000"
            value={draft.expectedPay}
            onChange={(e) => patch({ expectedPay: e.target.value })}
          />,
          'Optional. Only used when a form requires a number.',
        )}
        {question(
          'familyEmployers',
          'Companies you or a family member have worked for',
          <PillInput
            items={draft.familyEmployers}
            onChange={(familyEmployers) => patch({ familyEmployers })}
            label="Family employers"
            addLabel="Add company"
            placeholder="Company name"
          />,
          'Forms sometimes ask “Do you have relatives employed here?” The agent answers from this list.',
        )}
        {question(
          'selfId',
          'Voluntary self-identification',
          <div role="radiogroup" aria-labelledby="q-selfId">
            <Choice
              type="radio"
              name="selfId"
              checked={draft.selfId === 'decline'}
              onChange={() => patch({ selfId: 'decline' })}
            >
              Always choose “I don’t wish to answer”
            </Choice>
            <Choice
              type="radio"
              name="selfId"
              checked={draft.selfId === 'ask'}
              onChange={() => patch({ selfId: 'ask' })}
            >
              Ask me the first time each one comes up
            </Choice>
          </div>,
          'Gender, race and ethnicity, veteran and disability status. Always optional on applications.',
        )}
      </div>
      {error && <ErrorBox>We couldn’t finish setup. {error.message}</ErrorBox>}
      <SetupFooter
        onBack={() => navigate(paths.setupProfile)}
        onNext={() => void finish().catch(() => undefined)}
        loading={save.isPending || confirm.isPending}
        nextLabel="Confirm profile and finish"
      />
    </>
  );
}

/** Keeps a saved value selectable even when it's no longer in the generated list. */
const withCurrent = (options: string[], current: string | null) =>
  current && !options.includes(current) ? [current, ...options] : options;

function Question({
  id,
  label,
  hint,
  skipped,
  onToggleSkip,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  skipped: boolean;
  onToggleSkip: () => void;
  children: ReactNode;
}) {
  return (
    <div className={cx(styles.question, skipped && styles.skipped)}>
      <span className={styles.questionLabel} id={`q-${id}`}>
        {label}
        {hint && <span className={styles.questionHint}>{hint}</span>}
      </span>
      <LinkButton small onClick={onToggleSkip}>
        {skipped ? 'Undo skip' : 'Skip'}
      </LinkButton>
      <div className={styles.questionControl}>
        {skipped ? (
          <span className="small muted">Skipped. The agent will ask you if a form needs it.</span>
        ) : (
          children
        )}
      </div>
    </div>
  );
}
