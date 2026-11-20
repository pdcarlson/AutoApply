/** The voluntary self-identification questions of setup. */
import { RACES, type CommonAnswers, type Race } from '@/api/types';
import { Choice } from '@/components/ui/Choice';
import { Segmented } from '@/components/ui/Segmented';
import { inputClass } from '@/components/ui/classNames';
import { CommonQuestion, type SkipState } from './CommonQuestion';
import {
  DECLINE_LABEL,
  DECLINE_OPTION,
  DISABILITY_OPTIONS,
  questionLabelId,
  VETERAN_OPTIONS,
} from './commonQuestionOptions';
import styles from './SelfIdQuestions.module.css';

type RaceAnswer = Race | 'decline' | null;

const VETERAN_HINT =
  'Protected veterans include disabled veterans, recently separated veterans, and active duty wartime, campaign badge and Armed Forces service medal veterans.';

interface SelfIdQuestionsProps {
  draft: CommonAnswers;
  onChange: (changes: Partial<CommonAnswers>) => void;
  skips: SkipState;
}

/** Gender, ethnicity, race, veteran and disability questions, all optional. */
export function SelfIdQuestions({ draft, onChange, skips }: SelfIdQuestionsProps) {
  const isRaceAsked = draft.hispanicLatino === 'No';
  return (
    <>
      <div className={styles.questionGroup} id="q-selfIdGroup">
        <span className={styles.groupLabel}>Voluntary self-identification</span>
        <span className={styles.groupHint}>
          Most applications ask these. They’re always optional, and “I don’t wish to answer” is a
          fine answer to any of them.
        </span>
      </div>
      <CommonQuestion questionKey="gender" label="Gender" skips={skips}>
        <Segmented
          labelledBy={questionLabelId('gender')}
          options={['Male', 'Female', 'Non-binary', DECLINE_OPTION]}
          value={draft.gender}
          onChange={(gender) => onChange({ gender })}
        />
      </CommonQuestion>
      <CommonQuestion
        questionKey="hispanicLatino"
        label="Are you Hispanic or Latino?"
        skips={skips}
      >
        <Segmented
          labelledBy={questionLabelId('hispanicLatino')}
          options={['Yes', 'No', DECLINE_OPTION]}
          value={draft.hispanicLatino}
          onChange={(hispanicLatino) =>
            // Race is only asked of applicants who aren't Hispanic or Latino.
            onChange({ hispanicLatino, race: hispanicLatino === 'No' ? draft.race : null })
          }
        />
      </CommonQuestion>
      {isRaceAsked && (
        <CommonQuestion questionKey="race" label="Please identify your race" skips={skips}>
          <select
            className={inputClass(true)}
            aria-labelledby={questionLabelId('race')}
            value={draft.race ?? ''}
            onChange={(event) => onChange({ race: (event.target.value || null) as RaceAnswer })}
          >
            <option value="">Choose one</option>
            {RACES.map((race) => (
              <option key={race} value={race}>
                {race}
              </option>
            ))}
            <option value="decline">{DECLINE_LABEL}</option>
          </select>
        </CommonQuestion>
      )}
      <CommonQuestion
        questionKey="veteran"
        label="Veteran status"
        hint={VETERAN_HINT}
        skips={skips}
      >
        <RadioOptions
          name="veteran"
          options={VETERAN_OPTIONS}
          value={draft.veteran}
          onChange={(veteran) => onChange({ veteran })}
        />
      </CommonQuestion>
      <CommonQuestion questionKey="disability" label="Disability status" skips={skips}>
        <RadioOptions
          name="disability"
          options={DISABILITY_OPTIONS}
          value={draft.disability}
          onChange={(disability) => onChange({ disability })}
        />
      </CommonQuestion>
    </>
  );
}

interface RadioOptionsProps<T extends string> {
  /** The question key; also the radio group's `name`. */
  name: 'veteran' | 'disability';
  options: readonly { value: T; label: string }[];
  value: T | null;
  onChange: (value: T) => void;
}

function RadioOptions<T extends string>({ name, options, value, onChange }: RadioOptionsProps<T>) {
  return (
    <div role="radiogroup" aria-labelledby={questionLabelId(name)}>
      {options.map((option) => (
        <Choice
          key={option.value}
          type="radio"
          name={name}
          checked={value === option.value}
          onChange={() => onChange(option.value)}
        >
          {option.label}
        </Choice>
      ))}
    </div>
  );
}
