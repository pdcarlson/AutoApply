/**
 * A tiny stand-in for the backend agent so polling, progress, and state changes can be seen in
 * development. Each second of wall time is one step: open the form, fill one field, and stop on
 * a question, a CAPTCHA, or when the form is full.
 */
import type { AgentQuestion, ApplicationDetail, FilledField } from '@/api/types';
import { db, isoAgo, nextReference, screenshotFor, type MockJob } from './db';
import { DEFAULT_HANDOFF_REASON } from '@/features/inbox/HandoffPanel';

const STEP_MS = 1000;

export function advanceAgent(now = Date.now()) {
  const steps = Math.min(30, Math.floor((now - db.lastTick) / STEP_MS));
  if (steps <= 0) return;
  db.lastTick += steps * STEP_MS;
  for (let i = 0; i < steps; i++) step();
}

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
    Object.assign(job, {
      state: 'handoff',
      phase: null,
      currentField: null,
      reason: DEFAULT_HANDOFF_REASON,
    });
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
  job.fields.some((f) => f.label === job.plan.askAt?.question.field);
const byId = (id: string) => db.jobs.find((job) => job.id === id);
const removeFromQueue = (id: string) => (db.queue = db.queue.filter((q) => q !== id));

/** The order Applying now shows: running, then queued in order, then waiting. */
export function queueOrder(): string[] {
  const running = db.jobs.filter((j) => j.state === 'running').map((j) => j.id);
  const queued = db.queue.filter((id) => byId(id)?.state === 'queued');
  const waiting = db.jobs.filter((j) => j.state === 'waiting').map((j) => j.id);
  return [...running, ...queued, ...waiting];
}

// ===== Replies to questions =====

const UNSURE = /\b(maybe|depends|not sure|unsure|idk|possibly|might|perhaps|probably)\b/;
const NO = /\b(no|nope|nah|not|never|can't|cannot|won't|wouldn't|don't)\b/;
const YES =
  /\b(yes|yeah|yep|sure|ok|okay|definitely|absolutely|happy|willing|fine|i can|i would|i'd|i will|of course)\b/;
const AGREE = /^\s*(yes|yeah|yep|correct|right|looks good|sure|ok|okay)\b/i;

/** Rough reading of a reply, enough to exercise every branch of the question UI. */
export function interpretReply(question: AgentQuestion, text: string) {
  question.messages.push({ from: 'you', text });
  if (question.type === 'yesno') {
    const words = ` ${text.toLowerCase()} `;
    const value = UNSURE.test(words)
      ? null
      : NO.test(words)
        ? 'No'
        : YES.test(words)
          ? 'Yes'
          : null;
    if (!value) {
      const followups = question.messages.filter((m) => m.from === 'agent').length;
      question.messages.push({
        from: 'agent',
        text:
          followups >= 2
            ? 'I still can’t tell which one you mean. Pick Yes or No below, or reply again.'
            : 'This field only takes Yes or No. Tell me which one fits.',
      });
      if (followups >= 2) question.pickOptions = ['Yes', 'No'];
      return;
    }
    question.proposedAnswer = { value, confidence: 96 };
  } else if (question.type === 'draft' && question.draft) {
    const sentence = text
      .trim()
      .replace(/^./, (c) => c.toUpperCase())
      .replace(/([^.!?])$/, '$1.');
    question.proposedAnswer = {
      value: question.draft.text.replace(question.draft.gap, sentence),
      confidence: 94,
    };
  } else {
    const proposed = question.messages[0]?.text.match(/“(.+?)”/)?.[1];
    question.proposedAnswer =
      AGREE.test(text) && proposed
        ? { value: proposed, confidence: 97 }
        : { value: text.replace(/\.$/, ''), confidence: 95 };
  }
}

/** The user accepted the proposed answer: record it and send the job back to the front of the queue. */
export function acceptAnswer(job: MockJob, scope: 'all' | 'company') {
  const q = job.question!;
  const value = q.proposedAnswer!.value;
  const filled: FilledField = {
    label: q.field,
    value,
    source: 'You answered · today',
    sourceKind: 'you',
    confidence: q.proposedAnswer!.confidence,
  };
  job.plan.fields.splice(job.fields.length, 0, filled);
  job.fields.push(filled);
  db.answers.unshift({
    id: `a-${Date.now()}`,
    category: q.type === 'yesno' ? 'Logistics' : 'Experience',
    question: q.field,
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

/** Turns a finished job into a sent application. */
export function toApplication(job: MockJob, submittedBy: 'agent' | 'you'): ApplicationDetail {
  const now = new Date().toISOString();
  const byAgent = submittedBy === 'agent';
  return {
    id: `app-${job.id}`,
    jobId: job.id,
    company: job.company,
    role: job.role,
    location: job.location,
    ats: job.ats,
    url: job.url,
    status: 'submitted',
    submittedAt: now,
    submittedBy,
    confirmation: byAgent ? { reference: nextReference(job.ats), confirmedAt: now } : null,
    isNew: true,
    fields: [...job.fields],
    timeline: [
      {
        kind: 'muted',
        text: job.source === 'added' ? 'You added the link' : `New match from ${job.ats}`,
        at: job.addedAt ?? job.postedAt ?? isoAgo(0, 1),
      },
      ...(byAgent
        ? [
            {
              kind: 'muted' as const,
              text: 'Filled and held for your review',
              at: job.readyAt ?? now,
            },
            {
              kind: 'accent' as const,
              text: `Submitted via ${job.ats}, ${job.fields.length} fields. Confirmation page received.`,
              at: now,
            },
          ]
        : [
            { kind: 'amber' as const, text: 'Stopped at a CAPTCHA and handed to you', at: now },
            { kind: 'accent' as const, text: `You finished it on ${job.company}’s site`, at: now },
          ]),
      { kind: 'current', text: 'Waiting for a reply', at: now },
    ],
    screenshotUrl: byAgent ? screenshotFor(job) : null,
  };
}
