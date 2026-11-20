/** Setup questions about work authorization, timing, location and pay. */
import type { CommonAnswers } from '@/api/types';
import { DateInput } from '@/components/ui/DateInput';
import { PillInput } from '@/components/ui/PillInput';
import { Segmented } from '@/components/ui/Segmented';
import { inputClass } from '@/components/ui/classNames';
import { graduationOptions } from '@/lib/format';
import { CommonQuestion, type SkipState } from './CommonQuestion';
import { questionLabelId, withCurrent } from './commonQuestionOptions';

interface JobQuestionsProps {
  draft: CommonAnswers;
  onChange: (changes: Partial<CommonAnswers>) => void;
  skips: SkipState;
}

/** The questions most job forms ask before self-identification. */
export function JobQuestions({ draft, onChange, skips }: JobQuestionsProps) {
  const graduationChoices = withCurrent(graduationOptions(), draft.graduation);
  return (
    <>
      <CommonQuestion
        questionKey="workAuthorized"
        label="Are you legally authorized to work in the United States?"
        skips={skips}
      >
        <Segmented
          labelledBy={questionLabelId('workAuthorized')}
          options={['Yes', 'No']}
          value={draft.workAuthorized}
          onChange={(workAuthorized) => onChange({ workAuthorized })}
        />
      </CommonQuestion>
      <CommonQuestion
        questionKey="needsSponsorship"
        label="Will you now or in the future need visa sponsorship?"
        skips={skips}
      >
        <Segmented
          labelledBy={questionLabelId('needsSponsorship')}
          options={['Yes', 'No']}
          value={draft.needsSponsorship}
          onChange={(needsSponsorship) => onChange({ needsSponsorship })}
        />
      </CommonQuestion>
      <CommonQuestion questionKey="graduation" label="When do you graduate?" skips={skips}>
        <select
          className={inputClass(true)}
          aria-labelledby={questionLabelId('graduation')}
          value={draft.graduation ?? ''}
          onChange={(event) => onChange({ graduation: event.target.value || null })}
        >
          <option value="">Choose a month</option>
          {graduationChoices.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </CommonQuestion>
      <CommonQuestion questionKey="earliestStart" label="Earliest start date" skips={skips}>
        <DateInput
          labelledBy={questionLabelId('earliestStart')}
          value={draft.earliestStart ?? ''}
          onChange={(value) => onChange({ earliestStart: value || null })}
        />
      </CommonQuestion>
      <CommonQuestion questionKey="relocate" label="Willing to relocate?" skips={skips}>
        <Segmented
          labelledBy={questionLabelId('relocate')}
          options={['Yes', 'No', 'Depends']}
          value={draft.relocate}
          onChange={(relocate) => onChange({ relocate })}
        />
      </CommonQuestion>
      <CommonQuestion questionKey="locations" label="Where do you want to work?" skips={skips}>
        <PillInput
          items={draft.locations}
          onChange={(locations) => onChange({ locations })}
          label="Places"
          addLabel="Add place"
          placeholder="City, State or Remote"
        />
      </CommonQuestion>
      <CommonQuestion
        questionKey="expectedPay"
        label="Expected pay (per year)"
        hint="Optional. Only used when a form requires a number."
        skips={skips}
      >
        <input
          className={inputClass(true)}
          inputMode="numeric"
          aria-labelledby={questionLabelId('expectedPay')}
          placeholder="e.g. 85,000"
          value={draft.expectedPay}
          onChange={(event) => onChange({ expectedPay: event.target.value })}
        />
      </CommonQuestion>
      <CommonQuestion
        questionKey="familyEmployers"
        label="Companies you or a family member have worked for"
        hint="Forms sometimes ask “Do you have relatives employed here?” The agent answers from this list."
        skips={skips}
      >
        <PillInput
          items={draft.familyEmployers}
          onChange={(familyEmployers) => onChange({ familyEmployers })}
          label="Family employers"
          addLabel="Add company"
          placeholder="Company name"
        />
      </CommonQuestion>
    </>
  );
}
