/** Mock handlers for sent applications. */
import { http } from 'msw';
import type { ApplicationStatus } from '@/api/types';
import { db } from '@/mocks/db';
import { toApplicationSummary } from '@/mocks/wire';
import { apiPath, notFound, ok } from './respond';

/** Listing sent applications and moving them between statuses. */
export const applicationHandlers = [
  http.get(apiPath('/applications'), async () => {
    return ok(db.applications.map(toApplicationSummary));
  }),
  http.get(apiPath('/applications/:id'), async ({ params }) => {
    const application = db.applications.find((candidate) => candidate.id === params.id);
    return application ? ok(application) : notFound('Application');
  }),
  http.patch(apiPath('/applications/:id'), async ({ params, request }) => {
    const application = db.applications.find((candidate) => candidate.id === params.id);
    if (!application) return notFound('Application');
    const { status: next } = (await request.json()) as { status: ApplicationStatus };
    application.status = next;
    application.timeline = application.timeline.filter((event) => event.kind !== 'current');
    const label = next.charAt(0).toUpperCase() + next.slice(1);
    application.timeline.push({
      kind: next === 'rejected' ? 'red' : 'accent',
      text: `You marked it ${label}`,
      at: new Date().toISOString(),
    });
    if (next === 'submitted') {
      application.timeline.push({
        kind: 'current',
        text: 'Waiting for a reply',
        at: application.submittedAt,
      });
    }
    return ok(toApplicationSummary(application));
  }),
];
