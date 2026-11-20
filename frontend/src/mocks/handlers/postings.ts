/** Mock handlers for the job board. */
import { http } from 'msw';
import { db } from '@/mocks/db';
import { makeJob } from '@/mocks/fixtures/jobs';
import { toJob, toPosting } from '@/mocks/wire';
import { apiPath, fail, notFound, ok, unauthenticated } from './respond';

/** The job board and applying from it. */
export const postingHandlers = [
  http.get(apiPath('/postings'), async () => {
    if (!db.signedIn) return unauthenticated();
    return ok({
      postings: db.postings.map(toPosting),
      fetchedAt: new Date(db.lastTick).toISOString(),
      refreshing: false,
    });
  }),
  http.post(apiPath('/postings/:id/apply'), async ({ params }) => {
    const posting = db.postings.find((candidate) => candidate.id === params.id);
    if (!posting) return notFound('Posting');
    if (!db.session.profileConfirmed) {
      return fail(409, 'profile_not_confirmed', 'Confirm your profile before applying.');
    }
    if (toPosting(posting).status !== 'open') {
      return fail(409, 'already_in_inbox', 'That job is already in your Inbox.');
    }
    const job = makeJob({
      id: `job-${Date.now()}`,
      company: posting.company,
      role: posting.role,
      location: posting.location,
      ats: posting.ats,
      source: 'matched',
      ageDays: 0,
      reason: posting.fit.reasons.join(' · ') || 'Picked from Jobs',
      checks: posting.fit.reasons.map((text) => ({ status: 'ok', text })),
    });
    job.url = posting.url;
    job.state = 'queued';
    db.jobs.push(job);
    db.queue.push(job.id);
    db.lastTick = Date.now();
    return ok({ job: toJob(job), deferred: false });
  }),
];
