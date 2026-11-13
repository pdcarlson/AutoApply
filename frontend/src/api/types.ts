/**
 * API contract between the frontend and the Auto Apply backend.
 *
 * Every type here is a JSON shape the backend sends or receives. Dates are ISO 8601 strings:
 * full timestamps (`2026-10-20T13:41:00Z`) for moments, `YYYY-MM-DD` for calendar dates.
 * The endpoint for each shape is documented in src/api/endpoints.ts and in docs/api.md.
 */

// ===== Shared =====

export type Ats = 'Greenhouse' | 'Ashby';

/** Error body returned with any non-2xx status. `code` is stable; `message` is for people. */
export interface ApiErrorBody {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

// ===== Auth =====

export interface User {
  id: string;
  /** Display name, derived from the profile: "First Middle Last", skipping an empty middle name. */
  name: string;
  email: string;
}

export interface Session {
  user: User;
  /** False until the user finishes setup by confirming their profile. */
  profileConfirmed: boolean;
}

export interface GoogleSignInStart {
  /** Google's authorization URL. The browser is sent there; Google redirects back to the backend. */
  authorizationUrl: string;
}

// ===== Profile =====

export interface ProfileLink {
  id: string;
  label: string;
  url: string;
  /** Built-in links (Website, LinkedIn, GitHub) can't be renamed or removed. */
  fixed: boolean;
}

export interface CustomField {
  id: string;
  label: string;
  value: string;
}

export interface Education {
  id: string;
  school: string;
  degreeType: string;
  major: string;
  gpa: string;
  location: string;
  /** YYYY-MM-DD or empty. */
  start: string;
  /** YYYY-MM-DD or empty. */
  end: string;
  coursework: string;
}

/** A job, or a role shaped like one that isn't employment (a club office, volunteering). */
export type ExperienceKind = 'work' | 'leadership' | 'volunteer' | 'activity';

export const EXPERIENCE_KINDS: readonly { value: ExperienceKind; label: string }[] = [
  { value: 'work', label: 'Work' },
  { value: 'leadership', label: 'Leadership' },
  { value: 'volunteer', label: 'Volunteer' },
  { value: 'activity', label: 'Activity' },
];

export interface Experience {
  id: string;
  /** Only `work` counts as employment (current employer, work history). */
  kind: ExperienceKind;
  title: string;
  org: string;
  location: string;
  start: string;
  end: string;
  current: boolean;
  /** One bullet per line. */
  detail: string;
}

export interface Project {
  id: string;
  name: string;
  tech: string;
  detail: string;
}

export interface ResumeFile {
  name: string;
  sizeBytes: number;
  pageCount: number | null;
  uploadedAt: string;
}

/** Resume text the parser couldn't place into a profile field. */
export interface UnplacedSection {
  id: string;
  text: string;
  /** What accepting it does, e.g. "Add to Education". Null when it can only be left out. */
  suggestion: string | null;
}

export interface Profile {
  /** Required to finish setup. */
  firstName: string;
  /** Optional; empty when the user has none. */
  middleName: string;
  /** Required to finish setup. */
  lastName: string;
  email: string;
  phone: string;
  street: string;
  street2: string;
  city: string;
  state: string;
  zip: string;
  country: string;
  links: ProfileLink[];
  education: Education[];
  experience: Experience[];
  projects: Project[];
  skills: string[];
  custom: CustomField[];
  resume: ResumeFile | null;
  unplaced: UnplacedSection[];
}

/** Everything in Profile the user edits directly (resume and unplaced are managed separately). */
export type ProfileUpdate = Omit<Profile, 'resume' | 'unplaced'>;

// ===== Resume parsing =====

export type ResumeParseStatus = 'parsing' | 'done' | 'failed';

export interface ResumeParse {
  status: ResumeParseStatus;
  file: ResumeFile;
  /** One line per profile section the parser filled, in the order it finished them. */
  sections: { status: 'ok' | 'warn'; label: string }[];
  /** Set when status is `failed`. `unreadable` means the user should fill the profile by hand. */
  error: { code: 'unreadable' | 'invalid_type' | 'too_large'; message: string } | null;
}

// ===== Common questions & preferences =====

export type YesNo = 'Yes' | 'No';

export type CommonQuestionKey =
  | 'workAuthorized'
  | 'needsSponsorship'
  | 'graduation'
  | 'earliestStart'
  | 'relocate'
  | 'locations'
  | 'expectedPay'
  | 'familyEmployers'
  | SelfIdKey;

/** Voluntary self-identification questions; each one can be answered, declined, or skipped. */
export type SelfIdKey = 'gender' | 'hispanicLatino' | 'race' | 'veteran' | 'disability';

/** "I don't wish to answer", a valid answer to every self-ID question. */
export type Decline = 'decline';

export const RACES = [
  'American Indian or Alaska Native',
  'Asian',
  'Black or African American',
  'Native Hawaiian or Other Pacific Islander',
  'White',
  'Two or More Races',
] as const;

export type Race = (typeof RACES)[number];

export interface CommonAnswers {
  workAuthorized: YesNo | null;
  needsSponsorship: YesNo | null;
  /** "Month YYYY", e.g. "May 2027". */
  graduation: string | null;
  /** YYYY-MM-DD. */
  earliestStart: string | null;
  relocate: YesNo | 'Depends' | null;
  locations: string[];
  /** Free text; only used when a form requires a number. */
  expectedPay: string;
  familyEmployers: string[];
  // Self-ID: null means not answered yet, so the agent asks the first time a form has it.
  gender: 'Male' | 'Female' | 'Non-binary' | Decline | null;
  hispanicLatino: YesNo | Decline | null;
  /** Only asked when `hispanicLatino` is "No"; declining Hispanic/Latino declines race too. */
  race: Race | Decline | null;
  /** "Yes" means a protected veteran. */
  veteran: YesNo | Decline | null;
  disability: YesNo | Decline | null;
  skipped: CommonQuestionKey[];
}

export interface JobPreferences {
  roleTypes: string[];
  fullTime: boolean;
  internship: boolean;
}

// ===== Agent settings & status =====

export interface AgentSettings {
  /** 0–100. Values the agent scores below this come to the user as questions. */
  confidenceThreshold: number;
  /** 1–50 submissions per day. */
  dailyLimit: number;
}

export interface AgentStatus {
  paused: boolean;
  sentToday: number;
  dailyLimit: number;
  /** Job ids in the order the agent will work them: running first, then queued, then waiting. */
  queue: string[];
}

// ===== Jobs (Inbox) =====

export type JobSource = 'matched' | 'added';

export type JobState =
  | 'open' // in the Inbox, not approved yet
  | 'queued' // approved, waiting for its turn
  | 'running' // the agent is filling the form
  | 'waiting' // approved, held until tomorrow by the daily limit
  | 'needs_input' // paused on a question for the user
  | 'handoff' // stopped at a CAPTCHA/login; the user finishes on the employer's site
  | 'ready'; // filled and held for the user's review before submit

export type RunPhase = 'opening' | 'filling' | 'submitting' | 'confirming';

export interface ProfileCheck {
  status: 'ok' | 'warn' | 'bad';
  text: string;
}

export interface Job {
  id: string;
  company: string;
  role: string;
  location: string;
  ats: Ats;
  url: string;
  source: JobSource;
  /** When the posting went up (matched jobs). */
  postedAt: string | null;
  /** When the user added the link (added jobs). */
  addedAt: string | null;
  /** YYYY-MM-DD the posting closes, if known. */
  closesOn: string | null;
  /** One line on why it matched, or why it should be skipped. */
  reason: string;
  checks: ProfileCheck[];
  skipSuggested: boolean;
  state: JobState;
  phase: RunPhase | null;
  progress: { filled: number; total: number };
  /** How many fields the agent can fill vs. must ask about, at the current threshold. */
  formSummary: { totalFields: number; fieldsToAsk: number } | null;
  question: AgentQuestion | null;
  readyAt: string | null;
}

export type FieldSourceKind =
  | 'resume'
  | 'profile'
  | 'common_questions'
  | 'answer_bank'
  | 'you'
  | 'draft'
  | 'other';

export interface FilledField {
  label: string;
  value: string;
  /** Human-readable source, e.g. "Resume" or "You answered · Oct 16". */
  source: string;
  sourceKind: FieldSourceKind;
  /** 0–100. */
  confidence: number;
}

export interface JobDetail extends Job {
  fields: FilledField[];
  /** Label of the field being filled right now (state `running`). */
  currentField: string | null;
}

export type AnswerScope = 'all' | 'company';

/** A question the agent paused on. The conversation is driven by the backend. */
export interface AgentQuestion {
  id: string;
  type: 'confirm' | 'yesno' | 'draft';
  /** The form field's label, as the form asks it. */
  field: string;
  confidence: number;
  /** For `draft`: the text with a gap the user's reply fills. */
  draft: { text: string; gap: string } | null;
  messages: { from: 'agent' | 'you'; text: string }[];
  placeholder: string;
  /**
   * The form field's options, when it only takes one of them. The user picks one and there's
   * no reply box. Null when the field takes free text, so the user replies in their own words.
   */
  pickOptions: string[] | null;
  /** The answer the agent will enter once the user accepts it. Null while it still needs a reply. */
  proposedAnswer: { value: string; confidence: number } | null;
  defaultScope: AnswerScope;
}

export interface AddJobConflict {
  code: 'already_applied' | 'already_in_inbox';
  company: string;
  role: string;
  /** Set for `already_in_inbox`. */
  jobId?: string;
  /** Set for `already_applied`. */
  sentAt?: string;
}

export interface ApplyResult {
  /** Jobs that go out today. */
  queued: string[];
  /** Jobs held until tomorrow by the daily limit. */
  deferred: string[];
}

// ===== Applications =====

export type ApplicationStatus = 'submitted' | 'interviewing' | 'offer' | 'rejected';

export interface Application {
  id: string;
  jobId: string;
  company: string;
  role: string;
  location: string;
  ats: Ats;
  url: string;
  status: ApplicationStatus;
  submittedAt: string;
  /** `you` when the user finished it on the employer's site after a handoff. */
  submittedBy: 'agent' | 'you';
  confirmation: { reference: string; confirmedAt: string } | null;
  /** Submitted since the user last opened Applications. */
  isNew: boolean;
}

export type TimelineKind = 'muted' | 'accent' | 'amber' | 'red' | 'current';

export interface TimelineEvent {
  kind: TimelineKind;
  text: string;
  at: string;
}

export interface ApplicationDetail extends Application {
  fields: FilledField[];
  timeline: TimelineEvent[];
  /** Image saved when the form was submitted. Null when the user submitted it themselves. */
  screenshotUrl: string | null;
}

// ===== Answer bank =====

export const ANSWER_CATEGORIES = [
  'Eligibility',
  'Education',
  'Logistics',
  'Pay',
  'Experience',
  'Self-ID',
] as const;

export type AnswerCategory = (typeof ANSWER_CATEGORIES)[number];

export interface Answer {
  id: string;
  category: AnswerCategory;
  question: string;
  answer: string;
  /** Where it came from, e.g. "Onboarding · common questions". */
  source: string;
  /** Only used for this company when set. */
  company: string | null;
  timesUsed: number;
  lastUsedAt: string | null;
  /** Other wordings of the question this answer matched. */
  alsoMatches: { wording: string; seenOn: string }[];
  usedOn: { company: string; at: string; note: string | null }[];
  /** Saved from a reply in the last day. */
  savedRecently: boolean;
}

export interface AnswerInput {
  category: AnswerCategory;
  question: string;
  answer: string;
  company: string | null;
}
