/** The jobs the mock Inbox starts with. */
import type { Ats, JobDetail, JobSource } from '@/api/types';
import type { MockFormPlan } from '@/mocks/types';
import { agentQuestion } from './forms';

/** What a fixture says about a job; `makeJob` fills in the rest. */
export interface JobSeed {
  id: string;
  company: string;
  role: string;
  location: string;
  ats: Ats;
  source: JobSource;
  ageDays: number;
  reason: string;
  checks: JobDetail['checks'];
  skipSuggested?: boolean;
  closesInDays?: number;
  plan?: Partial<MockFormPlan>;
}

const ACME_SEED: JobSeed = {
  id: 'job-101',
  company: 'Acme Robotics',
  role: 'Software Engineer, New Grad',
  location: 'Chicago, IL',
  ats: 'Greenhouse',
  source: 'added',
  ageDays: 0,
  closesInDays: 9,
  reason: 'TypeScript and React match · asks for 1 year of experience',
  checks: [
    { status: 'ok', text: 'B.S. Computer Science: you have it' },
    { status: 'ok', text: 'TypeScript and React: on your profile' },
    {
      status: 'warn',
      text: 'Asks for 1 year of professional experience. Your profile has part-time work only.',
    },
  ],
  plan: {
    emailCode: true,
    askAt: {
      index: 6,
      question: agentQuestion(
        'q-101',
        'draft',
        'Why do you want to work at Acme Robotics?',
        41,
        'I drafted this from your profile, but I don’t know why you picked Acme, so I left a gap instead of guessing. What draws you to them? A sentence in your own words is enough.',
        {
          draft: {
            text: 'The role works in React and TypeScript, which I used to build a course planner for my classmates. [Your reason for choosing Acme]',
            gap: '[Your reason for choosing Acme]',
          },
          placeholder: 'e.g. I want my code on robots that leave the lab.',
        },
      ),
    },
  },
};

const INITECH_SEED: JobSeed = {
  id: 'job-103',
  company: 'Initech',
  role: 'Associate Software Engineer',
  location: 'Austin, TX',
  ats: 'Greenhouse',
  source: 'added',
  ageDays: 1,
  reason: 'Paused on 1 question the form asks',
  checks: [
    { status: 'ok', text: 'B.S. Computer Science: you have it' },
    { status: 'warn', text: 'Austin, TX isn’t on your list of places' },
  ],
  plan: {
    askAt: {
      index: 4,
      question: agentQuestion(
        'q-103',
        'yesno',
        'Willing to work on-site in Austin, TX, four days a week?',
        35,
        'Nothing in your profile answers this, and Austin, TX isn’t on your list of places. Pick one.',
        { placeholder: 'e.g. Yes', pickOptions: ['Yes', 'No'] },
      ),
    },
  },
};

/** Every starting job, in Inbox order. */
export const JOB_SEEDS: JobSeed[] = [
  ACME_SEED,
  {
    id: 'job-102',
    company: 'Globex',
    role: 'Frontend Engineer, New Grad',
    location: 'Remote (US)',
    ats: 'Ashby',
    source: 'matched',
    ageDays: 0,
    reason: 'React and TypeScript match · remote',
    checks: [
      { status: 'ok', text: 'React and TypeScript: on your profile' },
      { status: 'ok', text: 'Remote (US): on your list' },
      { status: 'ok', text: 'New grad role starting summer 2027' },
    ],
  },
  INITECH_SEED,
  {
    id: 'job-104',
    company: 'Hooli',
    role: 'Software Engineer I',
    location: 'New York, NY',
    ats: 'Greenhouse',
    source: 'matched',
    ageDays: 2,
    reason: 'Python and SQL match',
    checks: [
      { status: 'ok', text: 'Python and SQL: on your profile' },
      { status: 'ok', text: 'New York, NY: on your list' },
    ],
    plan: { captcha: true },
  },
  {
    id: 'job-105',
    company: 'Umbrella Health',
    role: 'Junior Java Developer',
    location: 'Remote (US)',
    ats: 'Ashby',
    source: 'matched',
    ageDays: 3,
    reason: 'Java matches · Spring Boot isn’t on your profile',
    checks: [
      { status: 'ok', text: 'Remote (US): on your list' },
      { status: 'warn', text: 'Spring Boot and AWS: not on your profile' },
    ],
  },
  {
    id: 'job-106',
    company: 'Stark Analytics',
    role: 'Data Engineer',
    location: 'Boston, MA',
    ats: 'Greenhouse',
    source: 'added',
    ageDays: 2,
    skipSuggested: true,
    closesInDays: 3,
    reason: 'Requires 3+ years of professional experience',
    checks: [
      { status: 'bad', text: 'Requires 3+ years of professional experience' },
      { status: 'ok', text: 'SQL: on your profile' },
    ],
  },
  {
    id: 'job-107',
    company: 'Wayne Logistics',
    role: 'Software Engineer, New Grad',
    location: 'Remote (US)',
    ats: 'Greenhouse',
    source: 'added',
    ageDays: 0,
    reason: 'Filled and waiting for your review',
    checks: [{ status: 'ok', text: 'TypeScript and SQL: on your profile' }],
  },
];
