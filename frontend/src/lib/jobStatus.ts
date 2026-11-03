/**
 * Display rules for jobs and applications: labels, chip tones, and progress. Pure functions of
 * the data the backend sends, so every screen describes a job the same way.
 */
import type { ApplicationStatus, Job, JobState } from '@/api/types';
import { formatDay } from './format';

export type Tone = 'teal' | 'amber' | 'red' | 'grey';

/** States shown in the Inbox list. `ready` jobs live under Applications instead. */
export const INBOX_STATES: readonly JobState[] = [
  'open',
  'needs_input',
  'handoff',
  'queued',
  'running',
  'waiting',
];

/** Jobs that still need something from the user before the agent can take them. */
export const isWaitingOnUser = (job: Job) =>
  job.state === 'open' || job.state === 'needs_input' || job.state === 'handoff';

/** Approved jobs the agent is working through. */
export const isInProgress = (job: Job) =>
  job.state === 'queued' || job.state === 'running' || job.state === 'waiting';

/** Newest first, by when it was added or posted. */
export const byNewest = (a: Job, b: Job) => jobTime(b) - jobTime(a);

const jobTime = (job: Job) => Date.parse(job.addedAt ?? job.postedAt ?? '') || 0;

/** The day shown in the Inbox date column, and what it means. */
export function jobDate(job: Job): { day: string; label: 'Added' | 'Posted' } {
  const value = job.source === 'added' ? job.addedAt : job.postedAt;
  return {
    day: value ? formatDay(value) : '—',
    label: job.source === 'added' ? 'Added' : 'Posted',
  };
}

/** "Filling form · 6 of 18 fields", "Queued, starting soon", etc. Empty for idle jobs. */
export function runStatusText(job: Job, paused: boolean): string {
  const { filled, total } = job.progress;
  switch (job.state) {
    case 'running':
      switch (job.phase) {
        case 'opening':
          return 'Opening the form in a fresh browser';
        case 'submitting':
          return 'Saving a screenshot, then submitting';
        case 'confirming':
          return 'Checking for the confirmation page';
        default:
          return `Filling form · ${filled} of ${total} fields`;
      }
    case 'ready':
      return 'Filled · waiting for your review';
    case 'queued':
      return paused ? 'Queued · the queue is paused' : 'Queued, starting soon';
    case 'waiting':
      return 'Waits until tomorrow · daily limit';
    case 'needs_input':
      return `Paused on 1 question · ${filled} of ${total} fields`;
    case 'handoff':
      return 'Stopped at a CAPTCHA. The last step is yours.';
    default:
      return '';
  }
}

/** 0–100 for the progress bar. Never quite 100 until the job is ready. */
export function progressPercent(job: Job): number {
  const { filled, total } = job.progress;
  const filling = total ? Math.round((92 * filled) / total) : 0;
  switch (job.state) {
    case 'running':
      if (job.phase === 'opening') return 3;
      if (job.phase === 'submitting') return 95;
      if (job.phase === 'confirming') return 99;
      return Math.max(3, filling);
    case 'ready':
      return 100;
    case 'needs_input':
    case 'handoff':
      return filling;
    default:
      return 0;
  }
}

/** The one-line summary under the job's name in the Inbox. */
export function jobSummaryLine(job: Job, paused: boolean): string {
  if (isInProgress(job) || job.state === 'handoff') return runStatusText(job, paused);
  if (job.state === 'needs_input') {
    return job.question?.type === 'draft'
      ? 'Paused on a written answer that needs your reason'
      : 'Paused on 1 question the form asks';
  }
  return job.reason;
}

/** Status chip for a job, or null when it has none (a plain open job). */
export function jobChip(job: Job): { tone: Tone; label: string } | null {
  switch (job.state) {
    case 'ready':
      return { tone: 'teal', label: 'Ready to submit' };
    case 'running':
      return { tone: 'teal', label: 'Applying' };
    case 'queued':
      return { tone: 'teal', label: 'Queued' };
    case 'waiting':
      return { tone: 'grey', label: 'Tomorrow' };
    case 'needs_input':
      return { tone: 'amber', label: 'Needs you' };
    case 'handoff':
      return { tone: 'amber', label: 'Finish on site' };
    default:
      return job.skipSuggested ? { tone: 'red', label: 'Skip suggested' } : null;
  }
}

/** "The agent can fill 17 of 18 fields on this form…". */
export function formSummaryText(job: Job): string | null {
  if (!job.formSummary) return null;
  const { totalFields, fieldsToAsk } = job.formSummary;
  if (!fieldsToAsk) {
    return `The agent can fill all ${totalFields} fields on this form from your profile and Answer bank, then hold it for your review before submitting.`;
  }
  return `The agent can fill ${totalFields - fieldsToAsk} of ${totalFields} fields. It will ask you about ${fieldsToAsk === 1 ? 'one' : fieldsToAsk} first, then hold the form for your review.`;
}

export const APPLICATION_STATUS_LABELS: Record<ApplicationStatus, string> = {
  submitted: 'Submitted',
  interviewing: 'Interviewing',
  offer: 'Offer',
  rejected: 'Rejected',
};

export const APPLICATION_STATUSES = Object.keys(APPLICATION_STATUS_LABELS) as ApplicationStatus[];

export const isClosedStatus = (status: ApplicationStatus) => status === 'rejected';

export function applicationChip(status: ApplicationStatus): { tone: Tone; label: string } {
  const label = APPLICATION_STATUS_LABELS[status];
  if (status === 'submitted') return { tone: 'grey', label };
  return { tone: isClosedStatus(status) ? 'red' : 'teal', label };
}

/** The usual next step for an application, offered as the drawer's primary action. */
export const NEXT_STATUS: Partial<Record<ApplicationStatus, ApplicationStatus>> = {
  submitted: 'interviewing',
  interviewing: 'offer',
  rejected: 'submitted',
};
