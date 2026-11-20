/** Mock handlers for the Inbox: listing, adding, approving, cancelling, and skipping jobs. */
import { http } from 'msw';
import type { Ats } from '@/api/types';
import { advanceAgent } from '@/mocks/agent';
import { db, type MockJob } from '@/mocks/db';
import { slugify } from '@/mocks/fixtures/helpers';
import { makeJob } from '@/mocks/fixtures/jobs';
import { toJob, toJobDetail } from '@/mocks/wire';
import { apiPath, fail, findJob, notFound, ok, unauthenticated } from './respond';

/** Skipped jobs, kept so Undo can restore them. */
const skipped = new Map<string, MockJob>();

/** Which supported board a link's host belongs to, if any. */
function atsForHost(host: string): Ats | null {
  if (host.endsWith('greenhouse.io')) return 'Greenhouse';
  if (host.endsWith('ashbyhq.com')) return 'Ashby';
  return null;
}

const titleCase = (text: string) =>
  text.replace(/[-_]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

/** The 409 for a link that is already in the Inbox or already applied to, if it is. */
function duplicateLinkError(url: string) {
  const existing = db.jobs.find((job) => job.url === url);
  if (existing) {
    return fail(409, 'already_in_inbox', 'That job is already in your Inbox.', {
      code: 'already_in_inbox',
      company: existing.company,
      role: existing.role,
      jobId: existing.id,
    });
  }
  const sent = db.applications.find((application) => application.url === url);
  if (sent) {
    return fail(409, 'already_applied', 'You already applied to this job.', {
      code: 'already_applied',
      company: sent.company,
      role: sent.role,
      sentAt: sent.submittedAt,
    });
  }
  return null;
}

/** A new Inbox job for a pasted link, named after the company in its path. */
function jobFromLink(link: URL, url: string, ats: Ats): MockJob {
  const companySlug = link.pathname.split('/').filter(Boolean)[0] ?? 'company';
  const job = makeJob({
    id: `job-${Date.now()}`,
    company: titleCase(companySlug),
    role: 'Software Engineer, New Grad',
    location: 'Remote (US)',
    ats,
    source: 'added',
    ageDays: 0,
    reason: 'Python and SQL match',
    checks: [
      { status: 'ok', text: 'Python and SQL: on your profile' },
      { status: 'ok', text: 'Remote (US): on your list' },
      { status: 'warn', text: 'The posting doesn’t say when the role starts' },
    ],
  });
  job.url = url || `https://boards.greenhouse.io/${slugify(companySlug)}`;
  job.addedAt = new Date().toISOString();
  return job;
}

/** The Inbox job list and the actions on it. */
export const jobHandlers = [
  http.get(apiPath('/jobs'), async () => {
    if (!db.signedIn) return unauthenticated();
    advanceAgent();
    return ok(db.jobs.map(toJob));
  }),
  http.get(apiPath('/jobs/:id'), async ({ params }) => {
    advanceAgent();
    const job = findJob(params.id);
    return job ? ok(toJobDetail(job)) : notFound('Job');
  }),
  http.post(apiPath('/jobs'), async ({ request }) => {
    const { url } = (await request.json()) as { url: string };
    let link: URL;
    try {
      link = new URL(url);
    } catch {
      return fail(
        422,
        'invalid_url',
        'Copy the job’s full address from your browser, then paste it here.',
      );
    }
    const ats = atsForHost(link.hostname);
    if (!ats) {
      return fail(
        422,
        'unsupported_site',
        `Auto Apply adds jobs from Greenhouse and Ashby links. This one is from ${link.hostname}.`,
      );
    }
    if (/closed/i.test(link.pathname)) {
      return fail(422, 'posting_closed', 'The company isn’t taking applications for it anymore.');
    }
    const normalized = url.replace(/\/$/, '');
    const duplicate = duplicateLinkError(normalized);
    if (duplicate) return duplicate;
    const job = jobFromLink(link, normalized, ats);
    db.jobs.push(job);
    return ok(toJob(job), 201);
  }),
  http.post(apiPath('/jobs/apply'), async ({ request }) => {
    if (!db.session.profileConfirmed) {
      return fail(409, 'profile_not_confirmed', 'Confirm your profile before applying.');
    }
    const { jobIds } = (await request.json()) as { jobIds: string[] };
    const room = Math.max(0, db.settings.dailyLimit - db.sentToday - db.queue.length);
    const queued: string[] = [];
    const deferred: string[] = [];
    for (const id of jobIds) {
      const job = findJob(id);
      if (!job || job.state !== 'open') continue;
      job.state = 'queued';
      db.queue.push(id);
      (queued.length < room ? queued : deferred).push(id);
    }
    db.lastTick = Date.now();
    return ok({ queued, deferred });
  }),
  http.post(apiPath('/jobs/cancel'), async ({ request }) => {
    const { jobIds } = (await request.json()) as { jobIds: string[] };
    for (const id of jobIds) {
      const job = findJob(id);
      if (job && ['queued', 'running', 'waiting'].includes(job.state)) {
        Object.assign(job, {
          state: 'open',
          phase: null,
          fields: [],
          currentField: null,
          progress: { ...job.progress, filled: 0 },
        });
      }
    }
    db.queue = db.queue.filter((id) => !jobIds.includes(id));
    return ok();
  }),
  http.post(apiPath('/jobs/:id/skip'), async ({ params }) => {
    const job = findJob(params.id);
    if (!job) return notFound('Job');
    db.jobs = db.jobs.filter((other) => other !== job);
    skipped.set(job.id, job);
    return ok();
  }),
  http.post(apiPath('/jobs/:id/restore'), async ({ params }) => {
    const job = skipped.get(String(params.id));
    if (!job) return notFound('Job');
    skipped.delete(job.id);
    db.jobs.push(job);
    return ok(toJob(job));
  }),
];
