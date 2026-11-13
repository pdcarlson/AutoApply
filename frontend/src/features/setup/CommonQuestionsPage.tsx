import { useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router';
import { RACES, type CommonAnswers, type CommonQuestionKey, type Race } from '@/api/types';
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
        <div className={styles.questionGroup} id="q-selfIdGroup">
          <span className={styles.questionLabel}>Voluntary self-identification</span>
          <span className={styles.questionHint}>
            Most applications ask these. They’re always optional, and “I don’t wish to answer” is a
            fine answer to any of them.
          </span>
        </div>
        {question(
          'gender',
          'Gender',
          <Segmented
            labelledBy="q-gender"
            options={['Male', 'Female', 'Non-binary', DECLINE_OPTION]}
            value={draft.gender}
            onChange={(gender) => patch({ gender })}
          />,
        )}
        {question(
          'hispanicLatino',
          'Are you Hispanic or Latino?',
          <Segmented
            labelledBy="q-hispanicLatino"
            options={['Yes', 'No', DECLINE_OPTION]}
            value={draft.hispanicLatino}
            onChange={(hispanicLatino) =>
              // Race is only asked of applicants who aren't Hispanic or Latino
              patch({ hispanicLatino, race: hispanicLatino === 'No' ? draft.race : null })
            }
          />,
        )}
        {draft.hispanicLatino === 'No' &&
          question(
            'race',
            'Please identify your race',
            <select
              className={inputClass(true)}
              aria-labelledby="q-race"
              value={draft.race ?? ''}
              onChange={(e) => patch({ race: (e.target.value || null) as Race | 'decline' | null })}
            >
              <option value="">Choose one</option>
              {RACES.map((race) => (
                <option key={race} value={race}>
                  {race}
                </option>
              ))}
              <option value="decline">{DECLINE_LABEL}</option>
            </select>,
          )}
        {question(
          'veteran',
          'Veteran status',
          <div role="radiogroup" aria-labelledby="q-veteran">
            {VETERAN_OPTIONS.map(({ value, label }) => (
              <Choice
                key={value}
                type="radio"
                name="veteran"
                checked={draft.veteran === value}
                onChange={() => patch({ veteran: value })}
              >
                {label}
              </Choice>
            ))}
          </div>,
          'Protected veterans include disabled veterans, recently separated veterans, and active duty wartime, campaign badge and Armed Forces service medal veterans.',
        )}
        {question(
          'disability',
          'Disability status',
          <div role="radiogroup" aria-labelledby="q-disability">
            {DISABILITY_OPTIONS.map(({ value, label }) => (
              <Choice
                key={value}
                type="radio"
                name="disability"
                checked={draft.disability === value}
                onChange={() => patch({ disability: value })}
              >
                {label}
              </Choice>
            ))}
          </div>,
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

const DECLINE_LABEL = 'I don’t wish to answer';
const DECLINE_OPTION = { value: 'decline', label: DECLINE_LABEL } as const;

const VETERAN_OPTIONS = [
  { value: 'Yes', label: 'I am a protected veteran' },
  { value: 'No', label: 'I am not a protected veteran' },
  DECLINE_OPTION,
] as const;

const DISABILITY_OPTIONS = [
  { value: 'Yes', label: 'Yes, I have a disability (or had one in the past)' },
  { value: 'No', label: 'No, I don’t have a disability' },
  DECLINE_OPTION,
] as const;

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
