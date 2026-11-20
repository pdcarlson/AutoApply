/** A tiny stand-in for the backend agent, so polling, progress, and state changes can be seen. */
import type { AnswerScope, FilledField } from '@/api/types';
import { db, type MockJob } from './db';

// Each second of wall time is one step: open the form, fill one field, or stop on a question,
// a CAPTCHA, or a full form. Steps that came due between requests run on the next request.
const STEP_MS = 1000;
const MAX_CATCH_UP_STEPS = 30;

/** Runs the steps that have come due since the last request. */
export function advanceAgent(now = Date.now()) {
  const steps = Math.min(MAX_CATCH_UP_STEPS, Math.floor((now - db.lastTick) / STEP_MS));
  if (steps <= 0) return;
  db.lastTick += steps * STEP_MS;
  for (let i = 0; i < steps; i++) step();
}

/** One step: keep filling the running job, or start the next queued one. */
function step() {
  const running = db.jobs.find((job) => job.state === 'running');
  if (running) {
    fillNext(running);
    return;
  }
  if (db.paused) return;
  const next = db.queue.map(byId).find((job) => job?.state === 'queued');
  if (!next) return;
  if (db.sentToday >= db.settings.dailyLimit) {
    for (const job of db.jobs) if (job.state === 'queued') job.state = 'waiting';
    return;
  }
  Object.assign(next, { state: 'running', phase: next.fields.length ? 'filling' : 'opening' });
}

/** Fills the next field, or stops on a question, a CAPTCHA, or a finished form. */
function fillNext(job: MockJob) {
  if (job.phase === 'opening') {
    job.phase = 'filling';
    return;
  }
  const { plan } = job;
  const index = job.fields.length;

  if (plan.askAt && index === plan.askAt.index && !job.question && !answered(job)) {
    Object.assign(job, {
      state: 'needs_input',
      phase: null,
      currentField: null,
      question: structuredClone(plan.askAt.question),
    });
    removeFromQueue(job.id);
    return;
  }
  if (index < plan.fields.length) {
    job.fields.push(plan.fields[index]);
    job.progress.filled = job.fields.length;
    job.currentField = plan.fields[index + 1]?.label ?? null;
    return;
  }
  if (plan.captcha) {
    Object.assign(job, { state: 'handoff', phase: null, currentField: null });
  } else {
    Object.assign(job, {
      state: 'ready',
      phase: null,
      currentField: null,
      readyAt: new Date().toISOString(),
    });
  }
  removeFromQueue(job.id);
}

const answered = (job: MockJob) =>
  job.fields.some((field) => field.label === job.plan.askAt?.question.field);
const byId = (id: string) => db.jobs.find((job) => job.id === id);
const removeFromQueue = (id: string) => (db.queue = db.queue.filter((queued) => queued !== id));

/** The order Applying now shows: running, then queued in order, then waiting. */
export function queueOrder(): string[] {
  const running = db.jobs.filter((job) => job.state === 'running').map((job) => job.id);
  const queued = db.queue.filter((id) => byId(id)?.state === 'queued');
  const waiting = db.jobs.filter((job) => job.state === 'waiting').map((job) => job.id);
  return [...running, ...queued, ...waiting];
}

/** Saves the accepted answer and sends the job back to the front of the queue. */
export function acceptAnswer(job: MockJob, scope: AnswerScope) {
  const question = job.question!;
  const { value, confidence } = question.proposedAnswer!;
  const filled: FilledField = {
    label: question.field,
    value,
    source: 'You answered · today',
    sourceKind: 'you',
    confidence,
  };
  job.plan.fields.splice(job.fields.length, 0, filled);
  job.fields.push(filled);
  db.answers.unshift({
    id: `a-${Date.now()}`,
    category: question.type === 'yesno' ? 'Logistics' : 'Experience',
    question: question.field,
    answer: value,
    source: `You answered on ${job.company}’s form · today`,
    company: scope === 'company' ? job.company : null,
    timesUsed: 0,
    lastUsedAt: null,
    alsoMatches: [],
    usedOn: [],
    savedRecently: true,
  });
  Object.assign(job, {
    state: 'queued',
    question: null,
    progress: { ...job.progress, filled: job.fields.length },
  });
  db.queue = [job.id, ...db.queue.filter((id) => id !== job.id)];
}
