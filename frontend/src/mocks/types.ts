/** Shapes of the mock backend's in-memory state. */
import type {
  AgentQuestion,
  Answer,
  ApplicationDetail,
  CommonAnswers,
  FilledField,
  JobDetail,
  JobPreferences,
  Posting,
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
  /** After Submit, the site emails a verification code (all zeros is a wrong one). */
  emailCode?: boolean;
}

/** A job as the mock stores it: the wire shape plus the form it will fill. */
export interface MockJob extends JobDetail {
  plan: MockFormPlan;
}

/** Everything the mock backend remembers. */
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
  /** The job board, already ranked. `status` and `jobId` are worked out per request. */
  postings: Posting[];
  applications: ApplicationDetail[];
  answers: Answer[];
}
