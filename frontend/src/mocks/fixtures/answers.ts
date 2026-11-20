/** The saved answers the mock Answer bank starts with. */
import type { Answer } from '@/api/types';
import { isoAgo } from './helpers';

const ONBOARDING = 'Onboarding · common questions';

/** A saved answer; one that has been used shows a recent use on Cyberdyne's form. */
function savedAnswer(
  id: string,
  category: Answer['category'],
  question: string,
  answer: string,
  source: string,
  timesUsed: number,
  alsoMatches: Answer['alsoMatches'] = [],
): Answer {
  return {
    id,
    category,
    question,
    answer,
    source,
    company: null,
    timesUsed,
    lastUsedAt: timesUsed ? isoAgo(0, 3) : null,
    alsoMatches,
    usedOn: timesUsed ? [{ company: 'Cyberdyne Systems', at: isoAgo(0, 3), note: null }] : [],
    savedRecently: false,
  };
}

/** The starting Answer bank. */
export function seedAnswers(): Answer[] {
  return [
    savedAnswer(
      'a-1',
      'Eligibility',
      'Are you legally authorized to work in the United States?',
      'Yes',
      ONBOARDING,
      4,
      [{ wording: 'Are you eligible to work in the US?', seenOn: 'Greenhouse · Soylent Foods' }],
    ),
    savedAnswer(
      'a-2',
      'Eligibility',
      'Will you now or in the future require visa sponsorship?',
      'No',
      ONBOARDING,
      4,
    ),
    savedAnswer('a-3', 'Education', 'When do you graduate?', 'May 2027', 'Resume', 4),
    savedAnswer('a-4', 'Logistics', 'When can you start?', 'June 2027', ONBOARDING, 3),
    savedAnswer(
      'a-5',
      'Pay',
      'What are your salary expectations?',
      'Skip when optional. Ask me when a number is required.',
      ONBOARDING,
      1,
    ),
    savedAnswer(
      'a-6',
      'Experience',
      'How did you hear about this role?',
      'Online job board',
      'You answered on a form',
      4,
    ),
    savedAnswer('a-7', 'Self-ID', 'Gender', 'I don’t wish to answer', ONBOARDING, 4),
  ];
}
