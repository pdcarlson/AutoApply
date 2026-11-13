/**
 * Mock implementations of every endpoint in src/api/endpoints.ts, backed by the in-memory db.
 * They follow the documented contract, including error codes, so the UI's error paths can be
 * exercised too. Dev and tests only; never bundled into production.
 */
import { delay, http, HttpResponse, type JsonBodyType } from 'msw';
import type {
  AgentSettings,
  AgentStatus,
  AnswerInput,
  ApplicationStatus,
  CommonAnswers,
  Job,
  JobDetail,
  JobPreferences,
  ProfileUpdate,
} from '@/api/types';
import { acceptAnswer, advanceAgent, interpretReply, queueOrder, toApplication } from './agent';
import {
  db,
  displayName,
  emptyProfile,
  makeJob,
  PARSE_SECTIONS,
  parsedProfile,
  persist,
  resetDb,
  type MockJob,
} from './db';

const API = `${(import.meta.env.VITE_API_BASE_URL ?? '/api').replace(/\/$/, '')}`;
const path = (p: string) => `${API}${p}`;

/** Realistic-feeling latency in the browser; none in tests. */
const latency = () => (import.meta.env.MODE === 'test' ? Promise.resolve() : delay(250));

const ok = (body?: JsonBodyType, status = 200) => {
  persist();
  return body === undefined
    ? new HttpResponse(null, { status: 204 })
    : HttpResponse.json(body, { status });
};

const fail = (status: number, code: string, message: string, details?: Record<string, unknown>) =>
  HttpResponse.json({ code, message, details }, { status });

const unauthenticated = () => fail(401, 'unauthenticated', 'Sign in to continue.');
const notFound = (what: string) => fail(404, 'not_found', `${what} not found.`);

/** Strips the mock-only form plan before a job goes over the wire. */
function toJob(job: MockJob): Job {
  const { plan: _plan, fields: _fields, currentField: _current, ...rest } = job;
  return rest;
}

function toJobDetail(job: MockJob): JobDetail {
  const { plan: _plan, ...rest } = job;
  return rest;
}

/** The Session, with the user's display name taken from the profile like the backend does. */
const session = () => ({
  ...db.session,
  user: { ...db.session.user, name: displayName(db.profile) || db.session.user.name },
});

const findJob = (id: string | readonly string[] | undefined) =>
  db.jobs.find((job) => job.id === id);

function status(): AgentStatus {
  return {
    paused: db.paused,
    sentToday: db.sentToday,
    dailyLimit: db.settings.dailyLimit,
    queue: queueOrder(),
  };
}

/** FormData file entries; checked by shape because jsdom and Node have different File classes. */
const isFile = (value: FormDataEntryValue | null): value is File =>
  typeof value === 'object' && value !== null && 'name' in value && 'size' in value;

const slug = (s: string) => s.toLowerCase().replace(/[^a-z]+/g, '');
const titleCase = (s: string) => s.replace(/[-_]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

export const handlers = [
  // ===== Auth =====
  http.get(path('/session'), async () => {
    await latency();
    return db.signedIn ? ok(session()) : unauthenticated();
  }),
  http.post(path('/auth/google'), async () => {
    await latency();
    // Real backend: returns Google's URL. Mock: skip Google and come straight back signed in.
    db.signedIn = true;
    return ok({ authorizationUrl: '/auth/callback' });
  }),
  http.post(path('/auth/logout'), async () => {
    db.signedIn = false;
    return ok();
  }),

  // ===== Profile =====
  http.get(path('/profile'), async () => {
    await latency();
    return db.signedIn ? ok(db.profile) : unauthenticated();
  }),
  http.put(path('/profile'), async ({ request }) => {
    await latency();
    const update = (await request.json()) as ProfileUpdate;
    db.profile = { ...db.profile, ...update };
    return ok(db.profile);
  }),
  http.post(path('/profile/unplaced/:id'), async ({ params, request }) => {
    await latency();
    const { action } = (await request.json()) as { action: 'accept' | 'dismiss' };
    const section = db.profile.unplaced.find((u) => u.id === params.id);
    if (!section) return notFound('Section');
    if (action === 'accept' && db.profile.education[0]) {
      db.profile.education[0].coursework = section.text.replace(/^Relevant Coursework:\s*/i, '');
    }
    db.profile.unplaced = db.profile.unplaced.filter((u) => u.id !== section.id);
    return ok(db.profile);
  }),
  http.post(path('/profile/confirm'), async () => {
    await latency();
    db.session.profileConfirmed = true;
    return ok(session());
  }),

  // ===== Resume =====
  http.post(path('/resume'), async ({ request }) => {
    await latency();
    const file = (await request.formData()).get('file');
    if (!isFile(file)) return fail(422, 'invalid_type', 'Upload your resume as a PDF or DOCX.');
    if (!/\.(pdf|docx)$/i.test(file.name)) {
      return fail(
        422,
        'invalid_type',
        `${file.name} isn’t a PDF or DOCX. Upload your resume as a PDF or DOCX.`,
      );
    }
    if (file.size > 5 * 1024 * 1024)
      return fail(422, 'too_large', `${file.name} is over the 5 MB limit.`);
    const resume = {
      name: file.name,
      sizeBytes: file.size,
      pageCount: 1,
      uploadedAt: new Date().toISOString(),
    };
    db.resumeParse = { status: 'parsing', file: resume, sections: [], error: null };
    db.profile = { ...emptyProfile(), resume };
    return ok(db.resumeParse, 202);
  }),
  http.get(path('/resume/parse'), async () => {
    await latency();
    const parse = db.resumeParse;
    if (!parse) return notFound('Resume');
    if (parse.status === 'parsing') {
      parse.sections = PARSE_SECTIONS.slice(0, parse.sections.length + 2);
      if (parse.sections.length >= PARSE_SECTIONS.length) {
        parse.status = 'done';
        db.profile = parsedProfile(parse.file.name, parse.file.sizeBytes);
      }
    }
    return ok(parse);
  }),
  http.put(path('/resume/file'), async ({ request }) => {
    await latency();
    const file = (await request.formData()).get('file');
    if (!isFile(file) || !/\.(pdf|docx)$/i.test(file.name)) {
      return fail(422, 'invalid_type', 'Upload your resume as a PDF or DOCX.');
    }
    db.profile.resume = {
      name: file.name,
      sizeBytes: file.size,
      pageCount: 1,
      uploadedAt: new Date().toISOString(),
    };
    return ok(db.profile.resume);
  }),

  // ===== Common answers & preferences =====
  http.get(path('/common-answers'), async () => {
    await latency();
    return ok(db.commonAnswers);
  }),
  http.put(path('/common-answers'), async ({ request }) => {
    await latency();
    db.commonAnswers = (await request.json()) as CommonAnswers;
    return ok(db.commonAnswers);
  }),
  http.get(path('/preferences'), async () => {
    await latency();
    return ok(db.preferences);
  }),
  http.put(path('/preferences'), async ({ request }) => {
    db.preferences = (await request.json()) as JobPreferences;
    return ok(db.preferences);
  }),

  // ===== Agent =====
  http.get(path('/settings'), async () => {
    await latency();
    return ok(db.settings);
  }),
  http.patch(path('/settings'), async ({ request }) => {
    await latency();
    const patch = (await request.json()) as Partial<AgentSettings>;
    db.settings = { ...db.settings, ...patch };
    if (patch.dailyLimit !== undefined && db.sentToday < db.settings.dailyLimit) {
      for (const job of db.jobs) if (job.state === 'waiting') job.state = 'queued';
    }
    return ok(db.settings);
  }),
  http.get(path('/agent/status'), async () => {
    advanceAgent();
    return ok(status());
  }),
  http.post(path('/agent/pause'), async () => {
    db.paused = true;
    return ok(status());
  }),
  http.post(path('/agent/resume'), async () => {
    db.paused = false;
    db.lastTick = Date.now();
    return ok(status());
  }),

  // ===== Jobs =====
  http.get(path('/jobs'), async () => {
    await latency();
    if (!db.signedIn) return unauthenticated();
    advanceAgent();
    return ok(db.jobs.map(toJob));
  }),
  http.get(path('/jobs/:id'), async ({ params }) => {
    await latency();
    advanceAgent();
    const job = findJob(params.id);
    return job ? ok(toJobDetail(job)) : notFound('Job');
  }),
  http.post(path('/jobs'), async ({ request }) => {
    await delay(import.meta.env.MODE === 'test' ? 0 : 900);
    const { url } = (await request.json()) as { url: string };
    let parsed: URL;
    try {
      parsed = new URL(url);
    } catch {
      return fail(
        422,
        'invalid_url',
        'Copy the job’s full address from your browser, then paste it here.',
      );
    }
    const host = parsed.hostname;
    const ats = host.endsWith('greenhouse.io')
      ? 'Greenhouse'
      : host.endsWith('ashbyhq.com')
        ? 'Ashby'
        : null;
    if (!ats) {
      return fail(
        422,
        'unsupported_site',
        `Auto Apply adds jobs from Greenhouse and Ashby links. This one is from ${host}.`,
      );
    }
    if (/closed/i.test(parsed.pathname)) {
      return fail(422, 'posting_closed', 'The company isn’t taking applications for it anymore.');
    }
    const normalized = url.replace(/\/$/, '');
    const existing = db.jobs.find((j) => j.url === normalized);
    if (existing) {
      return fail(409, 'already_in_inbox', 'That job is already in your Inbox.', {
        code: 'already_in_inbox',
        company: existing.company,
        role: existing.role,
        jobId: existing.id,
      });
    }
    const sent = db.applications.find((a) => a.url === normalized);
    if (sent) {
      return fail(409, 'already_applied', 'You already applied to this job.', {
        code: 'already_applied',
        company: sent.company,
        role: sent.role,
        sentAt: sent.submittedAt,
      });
    }
    const companySlug = parsed.pathname.split('/').filter(Boolean)[0] ?? 'company';
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
    job.url = normalized || `https://boards.greenhouse.io/${slug(companySlug)}`;
    job.addedAt = new Date().toISOString();
    db.jobs.push(job);
    return ok(toJob(job), 201);
  }),
  http.post(path('/jobs/apply'), async ({ request }) => {
    await latency();
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
  http.post(path('/jobs/cancel'), async ({ request }) => {
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
  http.post(path('/jobs/:id/skip'), async ({ params }) => {
    const job = findJob(params.id);
    if (!job) return notFound('Job');
    db.jobs = db.jobs.filter((j) => j !== job);
    skipped.set(job.id, job);
    return ok();
  }),
  http.post(path('/jobs/:id/restore'), async ({ params }) => {
    const job = skipped.get(String(params.id));
    if (!job) return notFound('Job');
    skipped.delete(job.id);
    db.jobs.push(job);
    return ok(toJob(job));
  }),
  http.post(path('/jobs/:id/submit'), async ({ params }) => {
    await delay(import.meta.env.MODE === 'test' ? 0 : 1200);
    const job = findJob(params.id);
    if (!job || job.state !== 'ready')
      return fail(409, 'not_ready', 'This job isn’t waiting for review.');
    if (job.plan.emailCode) {
      const reason = `${job.ats} emailed you a verification code to finish this application. Find the email and enter the code here: the agent types it into the form and submits it.`;
      Object.assign(job, { state: 'handoff', asksForCode: true, reason });
      return fail(502, 'submit_unconfirmed', reason);
    }
    const app = toApplication(job, 'agent');
    db.applications.unshift(app);
    db.jobs = db.jobs.filter((j) => j !== job);
    db.sentToday += 1;
    const { fields: _f, timeline: _t, screenshotUrl: _s, ...summary } = app;
    return ok(summary);
  }),
  http.post(path('/jobs/:id/verification-code'), async ({ params, request }) => {
    await delay(import.meta.env.MODE === 'test' ? 0 : 1500);
    const job = findJob(params.id);
    if (!job || job.state !== 'handoff')
      return fail(409, 'not_handoff', 'This job isn’t waiting for you to finish it.');
    if (!job.asksForCode)
      return fail(409, 'no_code_window', 'This job isn’t waiting for an emailed code anymore.');
    const { code } = (await request.json()) as { code?: string };
    const trimmed = (code ?? '').replace(/\s+/g, '');
    if (!trimmed) return fail(422, 'invalid_code', 'Enter the code from the email.');
    if (/^0+$/.test(trimmed))
      return fail(
        422,
        'code_rejected',
        'The site didn’t take that code. Check that it’s from the newest email the site sent, and try again.',
      );
    const app = toApplication(job, 'agent');
    db.applications.unshift(app);
    db.jobs = db.jobs.filter((j) => j !== job);
    db.sentToday += 1;
    const { fields: _f, timeline: _t, screenshotUrl: _s, ...summary } = app;
    return ok(summary);
  }),
  http.post(path('/jobs/:id/mark-submitted'), async ({ params }) => {
    await latency();
    const job = findJob(params.id);
    if (!job || job.state !== 'handoff')
      return fail(409, 'not_handoff', 'This job isn’t waiting for you to finish it.');
    const app = toApplication(job, 'you');
    db.applications.unshift(app);
    db.jobs = db.jobs.filter((j) => j !== job);
    const { fields: _f, timeline: _t, screenshotUrl: _s, ...summary } = app;
    return ok(summary);
  }),

  // ===== Questions =====
  http.post(path('/jobs/:id/question/messages'), async ({ params, request }) => {
    await latency();
    const job = findJob(params.id);
    if (!job?.question) return notFound('Question');
    const { text } = (await request.json()) as { text: string };
    interpretReply(job.question, text);
    return ok(job.question);
  }),
  http.put(path('/jobs/:id/question/answer'), async ({ params, request }) => {
    const job = findJob(params.id);
    if (!job?.question) return notFound('Question');
    const { value } = (await request.json()) as { value: string };
    job.question.proposedAnswer = { value, confidence: 100 };
    return ok(job.question);
  }),
  http.delete(path('/jobs/:id/question/answer'), async ({ params }) => {
    const job = findJob(params.id);
    if (!job?.question) return notFound('Question');
    job.question.proposedAnswer = null;
    return ok(job.question);
  }),
  http.post(path('/jobs/:id/question/accept'), async ({ params, request }) => {
    await latency();
    const job = findJob(params.id);
    if (!job?.question?.proposedAnswer)
      return fail(409, 'no_answer', 'There’s no answer to use yet.');
    const { scope } = (await request.json()) as { scope: 'all' | 'company' };
    acceptAnswer(job, scope);
    db.lastTick = Date.now();
    return ok(toJob(job));
  }),

  // ===== Applications =====
  http.get(path('/applications'), async () => {
    await latency();
    return ok(
      db.applications.map(({ fields: _f, timeline: _t, screenshotUrl: _s, ...summary }) => summary),
    );
  }),
  http.get(path('/applications/:id'), async ({ params }) => {
    await latency();
    const app = db.applications.find((a) => a.id === params.id);
    return app ? ok(app) : notFound('Application');
  }),
  http.patch(path('/applications/:id'), async ({ params, request }) => {
    await latency();
    const app = db.applications.find((a) => a.id === params.id);
    if (!app) return notFound('Application');
    const { status: next } = (await request.json()) as { status: ApplicationStatus };
    app.status = next;
    app.timeline = app.timeline.filter((e) => e.kind !== 'current');
    const label = next.charAt(0).toUpperCase() + next.slice(1);
    app.timeline.push({
      kind: next === 'rejected' ? 'red' : 'accent',
      text: `You marked it ${label}`,
      at: new Date().toISOString(),
    });
    if (next === 'submitted')
      app.timeline.push({ kind: 'current', text: 'Waiting for a reply', at: app.submittedAt });
    const { fields: _f, timeline: _t, screenshotUrl: _s, ...summary } = app;
    return ok(summary);
  }),

  // ===== Answer bank =====
  http.get(path('/answers'), async () => {
    await latency();
    return ok(db.answers);
  }),
  http.post(path('/answers'), async ({ request }) => {
    await latency();
    const input = (await request.json()) as AnswerInput;
    const answer = {
      ...input,
      id: `a-${Date.now()}`,
      source: 'You added it · today',
      timesUsed: 0,
      lastUsedAt: null,
      alsoMatches: [],
      usedOn: [],
      savedRecently: false,
    };
    db.answers.unshift(answer);
    return ok(answer, 201);
  }),
  http.patch(path('/answers/:id'), async ({ params, request }) => {
    await latency();
    const answer = db.answers.find((a) => a.id === params.id);
    if (!answer) return notFound('Answer');
    Object.assign(answer, (await request.json()) as Partial<AnswerInput>);
    return ok(answer);
  }),
  http.delete(path('/answers/:id'), async ({ params }) => {
    db.answers = db.answers.filter((a) => a.id !== params.id);
    return ok();
  }),

  // ===== Account =====
  http.get(path('/account/export'), async () => {
    await latency();
    const data = {
      profile: db.profile,
      commonAnswers: db.commonAnswers,
      preferences: db.preferences,
      answers: db.answers,
      applications: db.applications.map(({ screenshotUrl: _s, ...app }) => app),
    };
    return new HttpResponse(JSON.stringify(data, null, 2), {
      headers: {
        'Content-Type': 'application/json',
        'Content-Disposition': 'attachment; filename="auto-apply-export.json"',
      },
    });
  }),
  http.delete(path('/account'), async () => {
    await latency();
    resetDb();
    return ok();
  }),
];

/** Skipped jobs, kept so Undo can restore them. Not persisted. */
const skipped = new Map<string, MockJob>();
