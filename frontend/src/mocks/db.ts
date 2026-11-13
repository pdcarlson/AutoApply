/**
 * In-memory stand-in for the backend, used only by the dev mock API and tests.
 * Fixtures are placeholder data so every screen can be exercised before the backend exists.
 * In the browser the state is kept in localStorage so a reload doesn't sign you out;
 * run `autoApplyMocks.reset()` in the console to start over.
 */
import type {
  AgentQuestion,
  Answer,
  ApplicationDetail,
  CommonAnswers,
  FilledField,
  JobDetail,
  JobPreferences,
  Profile,
  ResumeParse,
  Session,
} from '@/api/types';

/** What the mock agent will run into while filling a job's form. */
export interface MockFormPlan {
  fields: FilledField[];
  /** Index in `fields` where the agent stops to ask a question. */
  askAt?: { index: number; question: AgentQuestion };
  /** The form ends in a CAPTCHA. */
  captcha?: boolean;
}

export interface MockJob extends JobDetail {
  plan: MockFormPlan;
}

export interface MockDb {
  signedIn: boolean;
  session: Session;
  profile: Profile;
  resumeParse: ResumeParse | null;
  commonAnswers: CommonAnswers;
  preferences: JobPreferences;
  settings: { confidenceThreshold: number; dailyLimit: number };
  paused: boolean;
  sentToday: number;
  /** Job ids in queue order. */
  queue: string[];
  lastTick: number;
  jobs: MockJob[];
  applications: ApplicationDetail[];
  answers: Answer[];
}

// ===== Time helpers =====

const HOUR = 3_600_000;
export const isoAgo = (days: number, hours = 0) =>
  new Date(Date.now() - days * 24 * HOUR - hours * HOUR).toISOString();
const dateIn = (days: number) => new Date(Date.now() + days * 24 * HOUR).toISOString().slice(0, 10);

// ===== Fixtures =====

const USER = { id: 'user-1', name: 'Sam Rivera', email: 'sam.rivera@example.com' };

export const emptyProfile = (): Profile => ({
  firstName: 'Sam',
  middleName: '',
  lastName: 'Rivera',
  email: USER.email,
  phone: '',
  street: '',
  street2: '',
  city: '',
  state: '',
  zip: '',
  country: 'United States',
  links: [
    { id: 'web', label: 'Website / portfolio', url: '', fixed: true },
    { id: 'linkedin', label: 'LinkedIn', url: '', fixed: true },
    { id: 'github', label: 'GitHub', url: '', fixed: true },
  ],
  education: [],
  experience: [],
  projects: [],
  skills: [],
  custom: [],
  resume: null,
  unplaced: [],
});

/** What the mock parser "reads" out of any uploaded resume. */
export const parsedProfile = (fileName: string, sizeBytes: number): Profile => ({
  ...emptyProfile(),
  phone: '(555) 010-2233',
  street: '100 Example Street',
  street2: 'Apt 2',
  city: 'Springfield',
  state: 'IL',
  zip: '62701',
  links: [
    { id: 'web', label: 'Website / portfolio', url: '', fixed: true },
    { id: 'linkedin', label: 'LinkedIn', url: 'https://linkedin.com/in/example', fixed: true },
    { id: 'github', label: 'GitHub', url: 'https://github.com/example', fixed: true },
  ],
  education: [
    {
      id: 'ed-1',
      school: 'Example State University',
      degreeType: 'Bachelor of Science (B.S.)',
      major: 'Computer Science',
      gpa: '3.5',
      location: 'Springfield, IL',
      start: '2023-08-28',
      end: '2027-05-15',
      coursework: '',
    },
  ],
  experience: [
    {
      id: 'x-1',
      title: 'Teaching Assistant',
      org: 'Example State University',
      location: 'Springfield, IL',
      start: '2025-01-13',
      end: '',
      current: true,
      detail: 'Held weekly office hours for 60 students\nGraded programming assignments',
    },
  ],
  projects: [
    { id: 'p-1', name: 'Course planner', tech: 'React, TypeScript', detail: '' },
    {
      id: 'p-2',
      name: 'Study group bot',
      tech: 'Python',
      detail: 'Posts daily practice problems to a class chat',
    },
  ],
  skills: ['TypeScript', 'React', 'Python', 'SQL', 'Git'],
  resume: { name: fileName, sizeBytes, pageCount: 1, uploadedAt: new Date().toISOString() },
  unplaced: [
    {
      id: 'un-1',
      text: 'Relevant Coursework: Data Structures, Operating Systems, Software Design',
      suggestion: 'Add to Education',
    },
  ],
});

export const PARSE_SECTIONS: ResumeParse['sections'] = [
  { status: 'ok', label: 'Contact info · 4 fields' },
  { status: 'ok', label: 'Education · Example State University' },
  { status: 'ok', label: 'Experience · 1 role' },
  { status: 'ok', label: 'Projects · 2' },
  { status: 'ok', label: 'Skills · 5' },
  { status: 'warn', label: '1 section we couldn’t place' },
];

const field = (
  label: string,
  value: string,
  source: string,
  sourceKind: FilledField['sourceKind'],
  confidence: number,
): FilledField => ({ label, value, source, sourceKind, confidence });

const baseFields = (company: string): FilledField[] => [
  field('First name', 'Sam', 'Resume', 'resume', 99),
  field('Last name', 'Rivera', 'Resume', 'resume', 99),
  field('Email', USER.email, 'Resume', 'resume', 99),
  field('Phone', '(555) 010-2233', 'Resume', 'resume', 98),
  field('Resume', 'Resume.pdf', 'Uploaded as-is', 'profile', 100),
  field('School', 'Example State University', 'Resume', 'resume', 99),
  field('Authorized to work in the US?', 'Yes', 'Common questions', 'common_questions', 99),
  field('Need visa sponsorship now or later?', 'No', 'Common questions', 'common_questions', 99),
  field('How did you hear about this role?', 'Online job board', 'Answer bank', 'answer_bank', 96),
  field(`Relatives employed at ${company}?`, 'No', 'Family employers list', 'common_questions', 97),
  field('Gender', 'I don’t wish to answer', 'Common questions', 'common_questions', 99),
];

const question = (
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

interface JobSeed {
  id: string;
  company: string;
  role: string;
  location: string;
  ats: 'Greenhouse' | 'Ashby';
  source: 'matched' | 'added';
  ageDays: number;
  reason: string;
  checks: JobDetail['checks'];
  skipSuggested?: boolean;
  closesInDays?: number;
  plan?: Partial<MockFormPlan>;
}

const slug = (s: string) => s.toLowerCase().replace(/[^a-z]+/g, '');

export function makeJob(seed: JobSeed): MockJob {
  const fields = seed.plan?.fields ?? baseFields(seed.company);
  const plan: MockFormPlan = { fields, ...seed.plan };
  const at = isoAgo(seed.ageDays, 2);
  const asks = plan.askAt ? 1 : 0;
  return {
    id: seed.id,
    company: seed.company,
    role: seed.role,
    location: seed.location,
    ats: seed.ats,
    url:
      seed.ats === 'Greenhouse'
        ? `https://boards.greenhouse.io/${slug(seed.company)}/jobs/${seed.id.replace(/\D/g, '') || '1001'}`
        : `https://jobs.ashbyhq.com/${slug(seed.company)}/${seed.id}`,
    source: seed.source,
    postedAt: seed.source === 'matched' ? at : null,
    addedAt: seed.source === 'added' ? at : null,
    closesOn: seed.closesInDays === undefined ? null : dateIn(seed.closesInDays),
    reason: seed.reason,
    checks: seed.checks,
    skipSuggested: seed.skipSuggested ?? false,
    state: 'open',
    phase: null,
    progress: { filled: 0, total: fields.length + asks + (plan.captcha ? 1 : 0) },
    formSummary: { totalFields: fields.length + asks, fieldsToAsk: asks },
    question: null,
    readyAt: null,
    fields: [],
    currentField: null,
    plan,
  };
}

function seedJobs(): MockJob[] {
  const jobs = [
    makeJob({
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
        askAt: {
          index: 6,
          question: question(
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
    }),
    makeJob({
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
    }),
    makeJob({
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
          question: question(
            'q-103',
            'yesno',
            'Willing to work on-site in Austin, TX, four days a week?',
            35,
            'Nothing in your profile answers this, and Austin, TX isn’t on your list of places. Reply in your own words.',
            { placeholder: 'e.g. Yes, I’d move for this one' },
          ),
        },
      },
    }),
    makeJob({
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
    }),
    makeJob({
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
    }),
    makeJob({
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
    }),
    makeJob({
      id: 'job-107',
      company: 'Wayne Logistics',
      role: 'Software Engineer, New Grad',
      location: 'Remote (US)',
      ats: 'Greenhouse',
      source: 'added',
      ageDays: 0,
      reason: 'Filled and waiting for your review',
      checks: [{ status: 'ok', text: 'TypeScript and SQL: on your profile' }],
    }),
  ];

  // Start a few in later states so every screen has something to show.
  const needs = jobs.find((j) => j.id === 'job-103')!;
  pauseOnQuestion(needs);
  const ready = jobs.find((j) => j.id === 'job-107')!;
  Object.assign(ready, {
    state: 'ready',
    fields: [...ready.plan.fields],
    progress: { filled: ready.plan.fields.length, total: ready.plan.fields.length },
    readyAt: isoAgo(0, 1),
  });
  return jobs;
}

/** Moves a job to the point where its plan asks a question. */
export function pauseOnQuestion(job: MockJob) {
  const ask = job.plan.askAt!;
  Object.assign(job, {
    state: 'needs_input',
    phase: null,
    fields: job.plan.fields.slice(0, ask.index),
    progress: { ...job.progress, filled: ask.index },
    question: structuredClone(ask.question),
  });
}

const SCREENSHOT_STYLE = 'font-family:Arial,sans-serif;font-size:13px;fill:#262626';

/** A stand-in for the screenshot the backend saves at submit time. */
export function screenshotFor(app: { company: string; role: string; fields: FilledField[] }) {
  const rows = app.fields
    .slice(0, 10)
    .map(
      (f, i) =>
        `<text x="24" y="${92 + i * 44}" style="${SCREENSHOT_STYLE};fill:#707070">${escapeXml(f.label)}</text>` +
        `<rect x="24" y="${98 + i * 44}" width="552" height="22" rx="3" fill="#f7f7f7" stroke="#d0d0d0"/>` +
        `<text x="32" y="${114 + i * 44}" style="${SCREENSHOT_STYLE}">${escapeXml(f.value)}</text>`,
    )
    .join('');
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="600" height="560" viewBox="0 0 600 560"><rect width="600" height="560" fill="#fff"/><rect width="600" height="28" fill="#ececec"/><text x="24" y="60" style="${SCREENSHOT_STYLE};font-size:20px;font-weight:bold">${escapeXml(app.role)} · ${escapeXml(app.company)}</text>${rows}<rect x="24" y="${100 + 10 * 44}" width="150" height="30" rx="3" fill="#333"/><text x="40" y="${120 + 10 * 44}" style="${SCREENSHOT_STYLE};fill:#fff;font-weight:bold">Submit application</text></svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

const escapeXml = (s: string) => s.replace(/[<>&"]/g, (c) => `&#${c.charCodeAt(0)};`);

let refSeq = 100_000;
export const nextReference = (ats: string) =>
  `${ats === 'Ashby' ? 'AS' : 'GH'}-${((refSeq += 7919) % 900_000) + 100_000}`;

function seedApplications(): ApplicationDetail[] {
  const app = (
    id: string,
    company: string,
    role: string,
    location: string,
    ats: 'Greenhouse' | 'Ashby',
    days: number,
    status: ApplicationDetail['status'],
  ): ApplicationDetail => {
    const submittedAt = isoAgo(days, 3);
    const fields = baseFields(company);
    const timeline: ApplicationDetail['timeline'] = [
      { kind: 'muted', text: `New match from ${ats}`, at: isoAgo(days + 1) },
      { kind: 'muted', text: 'You pressed Apply', at: isoAgo(days, 4) },
      { kind: 'accent', text: `Submitted via ${ats}, ${fields.length} fields`, at: submittedAt },
    ];
    if (status === 'interviewing')
      timeline.push({
        kind: 'accent',
        text: 'You marked it Interviewing',
        at: isoAgo(Math.max(0, days - 3)),
      });
    else if (status === 'rejected')
      timeline.push({
        kind: 'red',
        text: 'You marked it Rejected',
        at: isoAgo(Math.max(0, days - 5)),
      });
    else timeline.push({ kind: 'current', text: 'Waiting for a reply', at: submittedAt });
    return {
      id,
      jobId: `job-${id}`,
      company,
      role,
      location,
      ats,
      url: `https://boards.greenhouse.io/${slug(company)}/jobs/${id.replace(/\D/g, '')}`,
      status,
      submittedAt,
      submittedBy: 'agent',
      confirmation: { reference: nextReference(ats), confirmedAt: submittedAt },
      isNew: days === 0,
      fields,
      timeline,
      screenshotUrl: screenshotFor({ company, role, fields }),
    };
  };
  return [
    app(
      'app-201',
      'Cyberdyne Systems',
      'Backend Engineer I',
      'Remote (US)',
      'Ashby',
      0,
      'submitted',
    ),
    app(
      'app-202',
      'Soylent Foods',
      'Full-Stack Engineer, Early Career',
      'Remote (US)',
      'Greenhouse',
      4,
      'submitted',
    ),
    app(
      'app-203',
      'Vandelay Industries',
      'Junior Mobile Engineer',
      'Remote (US)',
      'Ashby',
      18,
      'interviewing',
    ),
    app(
      'app-204',
      'Massive Dynamic',
      'Software Engineer, New Grad',
      'New York, NY',
      'Greenhouse',
      29,
      'rejected',
    ),
  ];
}

function seedAnswers(): Answer[] {
  const answer = (
    id: string,
    category: Answer['category'],
    q: string,
    a: string,
    source: string,
    timesUsed: number,
    alsoMatches: Answer['alsoMatches'] = [],
  ): Answer => ({
    id,
    category,
    question: q,
    answer: a,
    source,
    company: null,
    timesUsed,
    lastUsedAt: timesUsed ? isoAgo(0, 3) : null,
    alsoMatches,
    usedOn: timesUsed ? [{ company: 'Cyberdyne Systems', at: isoAgo(0, 3), note: null }] : [],
    savedRecently: false,
  });
  return [
    answer(
      'a-1',
      'Eligibility',
      'Are you legally authorized to work in the United States?',
      'Yes',
      'Onboarding · common questions',
      4,
      [{ wording: 'Are you eligible to work in the US?', seenOn: 'Greenhouse · Soylent Foods' }],
    ),
    answer(
      'a-2',
      'Eligibility',
      'Will you now or in the future require visa sponsorship?',
      'No',
      'Onboarding · common questions',
      4,
    ),
    answer('a-3', 'Education', 'When do you graduate?', 'May 2027', 'Resume', 4),
    answer(
      'a-4',
      'Logistics',
      'When can you start?',
      'June 2027',
      'Onboarding · common questions',
      3,
    ),
    answer(
      'a-5',
      'Pay',
      'What are your salary expectations?',
      'Skip when optional. Ask me when a number is required.',
      'Onboarding · common questions',
      1,
    ),
    answer(
      'a-6',
      'Experience',
      'How did you hear about this role?',
      'Online job board',
      'You answered on a form',
      4,
    ),
    answer(
      'a-7',
      'Self-ID',
      'Voluntary self-identification (gender, race and ethnicity, veteran, disability)',
      'I don’t wish to answer',
      'Onboarding · common questions (the default)',
      4,
    ),
  ];
}

export function createDb(): MockDb {
  return {
    signedIn: false,
    session: { user: USER, profileConfirmed: false },
    profile: emptyProfile(),
    resumeParse: null,
    commonAnswers: {
      workAuthorized: null,
      needsSponsorship: null,
      graduation: null,
      earliestStart: null,
      relocate: null,
      locations: ['Remote (US)'],
      expectedPay: '',
      familyEmployers: [],
      selfId: 'decline',
      skipped: [],
    },
    preferences: {
      roleTypes: ['Software engineer', 'Frontend'],
      fullTime: true,
      internship: false,
    },
    settings: { confidenceThreshold: 90, dailyLimit: 25 },
    paused: false,
    sentToday: 1,
    queue: [],
    lastTick: Date.now(),
    jobs: seedJobs(),
    applications: seedApplications(),
    answers: seedAnswers(),
  };
}

// ===== Persistence (browser only) =====

const STORAGE_KEY = 'autoapply.mockdb.v1';
const canPersist =
  typeof window !== 'undefined' &&
  typeof localStorage !== 'undefined' &&
  import.meta.env.MODE !== 'test';

/** "First Middle Last" for the session's display name, like the backend builds it. */
export const displayName = (p: Pick<Profile, 'firstName' | 'middleName' | 'lastName'>) =>
  [p.firstName, p.middleName, p.lastName]
    .map((part) => part.trim())
    .filter(Boolean)
    .join(' ');

/** A profile saved before the name was split into three fields: "Mary Ann Smith" -> Mary/Ann/Smith. */
function migrateProfile(profile: Profile & { name?: string }): Profile {
  const { name, ...rest } = profile;
  if (name === undefined || rest.firstName !== undefined) return rest;
  const words = name.split(/\s+/).filter(Boolean);
  return {
    ...rest,
    firstName: words[0] ?? '',
    middleName: words.slice(1, -1).join(' '),
    lastName: words.length > 1 ? words[words.length - 1] : '',
  };
}

function load(): MockDb {
  if (!canPersist) return createDb();
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const saved = JSON.parse(stored) as MockDb;
      return { ...saved, profile: migrateProfile(saved.profile) };
    }
  } catch {
    // Corrupt or blocked storage: start fresh.
  }
  return createDb();
}

export let db: MockDb = load();

export function persist() {
  if (!canPersist) return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(db));
  } catch {
    // Storage full or blocked; the mock still works for this visit.
  }
}

export function resetDb(next: MockDb = createDb()) {
  db = next;
  persist();
}
