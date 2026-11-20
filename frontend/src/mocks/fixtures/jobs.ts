/** Builds mock Inbox jobs and moves them into the states the fixtures start in. */
import type { MockFormPlan, MockJob } from '@/mocks/types';
import { baseFields } from './forms';
import { dateIn, isoAgo, slugify } from './helpers';
import { JOB_SEEDS, type JobSeed } from './jobSeeds';

/** The posting's address on its board, made up from the company and id. */
function boardUrl(seed: JobSeed): string {
  const company = slugify(seed.company);
  if (seed.ats === 'Greenhouse') {
    return `https://boards.greenhouse.io/${company}/jobs/${seed.id.replace(/\D/g, '') || '1001'}`;
  }
  return `https://jobs.ashbyhq.com/${company}/${seed.id}`;
}

/** A fresh, open Inbox job. */
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
    url: boardUrl(seed),
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
    asksForCode: false,
    liveView: null,
    fields: [],
    currentField: null,
    plan,
  };
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

/** Marks a job as filled and waiting for review. */
function markReady(job: MockJob) {
  Object.assign(job, {
    state: 'ready',
    fields: [...job.plan.fields],
    progress: { filled: job.plan.fields.length, total: job.plan.fields.length },
    readyAt: isoAgo(0, 1),
  });
}

/** The starting Inbox, with a few jobs already in later states so every screen has content. */
export function seedJobs(): MockJob[] {
  // Cloned so a reset never sees state a previous session wrote into the fixtures.
  const jobs = JOB_SEEDS.map((seed) => makeJob(structuredClone(seed)));
  pauseOnQuestion(jobs.find((job) => job.id === 'job-103')!);
  markReady(jobs.find((job) => job.id === 'job-107')!);
  return jobs;
}
