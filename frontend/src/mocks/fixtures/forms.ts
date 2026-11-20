/** Builders for the form fields and questions the mock agent works through. */
import type { AgentQuestion, FilledField } from '@/api/types';
import { MOCK_USER } from './profile';

/** One filled form field. */
export const filledField = (
  label: string,
  value: string,
  source: string,
  sourceKind: FilledField['sourceKind'],
  confidence: number,
): FilledField => ({ label, value, source, sourceKind, confidence });

/** The fields every mock application form asks for. */
export const baseFields = (company: string): FilledField[] => [
  filledField('First name', 'Sam', 'Resume', 'resume', 99),
  filledField('Last name', 'Rivera', 'Resume', 'resume', 99),
  filledField('Email', MOCK_USER.email, 'Resume', 'resume', 99),
  filledField('Phone', '(555) 010-2233', 'Resume', 'resume', 98),
  filledField('Resume', 'Resume.pdf', 'Uploaded as-is', 'profile', 100),
  filledField('School', 'Example State University', 'Resume', 'resume', 99),
  filledField('Authorized to work in the US?', 'Yes', 'Common questions', 'common_questions', 99),
  filledField(
    'Need visa sponsorship now or later?',
    'No',
    'Common questions',
    'common_questions',
    99,
  ),
  filledField(
    'How did you hear about this role?',
    'Online job board',
    'Answer bank',
    'answer_bank',
    96,
  ),
  filledField(
    `Relatives employed at ${company}?`,
    'No',
    'Family employers list',
    'common_questions',
    97,
  ),
  filledField('Gender', 'I don’t wish to answer', 'Common questions', 'common_questions', 99),
];

/** A question the agent asks, opening with one message from the agent. */
export const agentQuestion = (
  id: string,
  type: AgentQuestion['type'],
  fieldLabel: string,
  confidence: number,
  firstMessage: string,
  extra: Partial<AgentQuestion> = {},
): AgentQuestion => ({
  id,
  type,
  field: fieldLabel,
  confidence,
  draft: null,
  messages: [{ from: 'agent', text: firstMessage }],
  placeholder: 'e.g. yes, or the right answer',
  pickOptions: null,
  proposedAnswer: null,
  defaultScope: 'company',
  ...extra,
});
