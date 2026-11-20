/** Turns finished mock jobs into sent applications. */
import type { Application, ApplicationDetail, TimelineEvent } from '@/api/types';
import { nextReference } from '@/mocks/fixtures/applications';
import { isoAgo } from '@/mocks/fixtures/helpers';
import { screenshotFor } from '@/mocks/fixtures/screenshot';
import { db, type MockJob } from './db';
import { toApplicationSummary } from './wire';

type Submitter = Application['submittedBy'];

/** The timeline steps between the job being found and the application going out. */
function submitSteps(job: MockJob, submittedBy: Submitter, now: string): TimelineEvent[] {
  if (submittedBy === 'agent') {
    return [
      { kind: 'muted', text: 'Filled and held for your review', at: job.readyAt ?? now },
      {
        kind: 'accent',
        text: `Submitted via ${job.ats}, ${job.fields.length} fields. Confirmation page received.`,
        at: now,
      },
    ];
  }
  return [
    { kind: 'amber', text: 'Stopped at a CAPTCHA and handed to you', at: now },
    { kind: 'accent', text: `You finished it on ${job.company}’s site`, at: now },
  ];
}

/** The application a finished job becomes. */
export function toApplication(job: MockJob, submittedBy: Submitter): ApplicationDetail {
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
      ...submitSteps(job, submittedBy, now),
      { kind: 'current', text: 'Waiting for a reply', at: now },
    ],
    screenshotUrl: byAgent ? screenshotFor(job) : null,
  };
}

/** Moves a job out of the Inbox into Applications. Only the agent's sends count toward the limit. */
export function submitJob(job: MockJob, submittedBy: Submitter): Application {
  const application = toApplication(job, submittedBy);
  db.applications.unshift(application);
  db.jobs = db.jobs.filter((other) => other !== job);
  if (submittedBy === 'agent') db.sentToday += 1;
  return toApplicationSummary(application);
}
