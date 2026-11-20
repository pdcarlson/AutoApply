/** The mock backend's in-memory state for tests. */
import type { CommonAnswers } from '@/api/types';
import { seedAnswers } from '@/mocks/fixtures/answers';
import { seedApplications } from '@/mocks/fixtures/applications';
import { seedJobs } from '@/mocks/fixtures/jobs';
import { seedPostings } from '@/mocks/fixtures/postings';
import { emptyProfile, MOCK_USER } from '@/mocks/fixtures/profile';
import type { MockDb } from './types';

export type { MockDb, MockFormPlan, MockJob } from './types';

/** Common questions before the user has answered any. */
const unansweredCommonAnswers = (): CommonAnswers => ({
  workAuthorized: null,
  needsSponsorship: null,
  graduation: null,
  earliestStart: null,
  relocate: null,
  locations: ['Remote (US)'],
  expectedPay: '',
  familyEmployers: [],
  gender: null,
  hispanicLatino: null,
  race: null,
  veteran: null,
  disability: null,
  skipped: [],
});

/** A brand-new, signed-out account with the fixture jobs, postings, and applications. */
export function createDb(): MockDb {
  return {
    signedIn: false,
    session: { user: MOCK_USER, profileConfirmed: false },
    profile: emptyProfile(),
    resumeParse: null,
    commonAnswers: unansweredCommonAnswers(),
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
    postings: seedPostings(),
    applications: seedApplications(),
    answers: seedAnswers(),
  };
}

/** The live state every mock handler reads and writes. */
export let db: MockDb = createDb();

/** Replaces the whole state, e.g. between tests or after deleting the account. */
export function resetDb(next: MockDb = createDb()) {
  db = next;
}
