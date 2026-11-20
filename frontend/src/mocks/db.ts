/** The mock backend's in-memory state, saved to localStorage in the browser. */
import type { CommonAnswers, Profile } from '@/api/types';
import { seedAnswers } from '@/mocks/fixtures/answers';
import { seedApplications } from '@/mocks/fixtures/applications';
import { seedJobs } from '@/mocks/fixtures/jobs';
import { seedPostings } from '@/mocks/fixtures/postings';
import { emptyProfile, MOCK_USER } from '@/mocks/fixtures/profile';
import type { MockDb } from './types';

export type { MockDb, MockFormPlan, MockJob } from './types';

const STORAGE_KEY = 'autoapply.mockdb.v1';

// Tests always start from fresh fixtures; only the dev browser keeps state across reloads.
const canPersist =
  typeof window !== 'undefined' &&
  typeof localStorage !== 'undefined' &&
  import.meta.env.MODE !== 'test';

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

/** The saved state, or a fresh one when nothing usable is saved. */
function loadDb(): MockDb {
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

/** The live state every mock handler reads and writes. */
export let db: MockDb = loadDb();

/** Saves the state so a reload keeps it (browser only). */
export function persist() {
  if (!canPersist) return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(db));
  } catch {
    // Storage full or blocked; the mock still works for this visit.
  }
}

/** Replaces the whole state, e.g. between tests or after deleting the account. */
export function resetDb(next: MockDb = createDb()) {
  db = next;
  persist();
}
