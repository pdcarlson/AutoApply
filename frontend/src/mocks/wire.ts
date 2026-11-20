/** Converts the mock's stored records into the JSON shapes the API sends. */
import type {
  AgentStatus,
  Application,
  ApplicationDetail,
  Job,
  JobDetail,
  Posting,
  Session,
} from '@/api/types';
import { displayName } from '@/mocks/fixtures/profile';
import { queueOrder } from './agent';
import { db, type MockJob } from './db';

/** A job for lists: no form plan and no field details. */
export function toJob(job: MockJob): Job {
  const { plan: _plan, fields: _fields, currentField: _currentField, ...rest } = job;
  return rest;
}

/** A job with its fields, minus the mock-only form plan. */
export function toJobDetail(job: MockJob): JobDetail {
  const { plan: _plan, ...rest } = job;
  return rest;
}

/** An application for lists: no fields, timeline, or screenshot. */
export function toApplicationSummary(application: ApplicationDetail): Application {
  const {
    fields: _fields,
    timeline: _timeline,
    screenshotUrl: _screenshotUrl,
    ...rest
  } = application;
  return rest;
}

/** A posting with where it stands now: in the Inbox, applied to, or still open. */
export function toPosting(posting: Posting): Posting {
  const job = db.jobs.find((candidate) => candidate.url === posting.url);
  if (job) return { ...posting, status: 'in_inbox', jobId: job.id };
  const applied = db.applications.some((application) => application.url === posting.url);
  return { ...posting, status: applied ? 'applied' : 'open' };
}

/** The Session, with the user's display name taken from the profile like the backend does. */
export function currentSession(): Session {
  return {
    ...db.session,
    user: { ...db.session.user, name: displayName(db.profile) || db.session.user.name },
  };
}

/** The agent's status as the API reports it. */
export function agentStatus(): AgentStatus {
  return {
    paused: db.paused,
    sentToday: db.sentToday,
    dailyLimit: db.settings.dailyLimit,
    queue: queueOrder(),
  };
}
