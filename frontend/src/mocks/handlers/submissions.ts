/** Mock handlers for submitting a reviewed job and finishing one handed to the user. */
import { http } from 'msw';
import { submitJob } from '@/mocks/submit';
import { apiPath, fail, findJob, ok } from './respond';

const notHandoff = () => fail(409, 'not_handoff', 'This job isn’t waiting for you to finish it.');

/** Submitting, entering an emailed code, and marking a handoff done. */
export const submissionHandlers = [
  http.post(apiPath('/jobs/:id/submit'), async ({ params }) => {
    const job = findJob(params.id);
    if (!job || job.state !== 'ready') {
      return fail(409, 'not_ready', 'This job isn’t waiting for review.');
    }
    if (job.plan.emailCode) {
      const reason = `${job.ats} emailed you a verification code to finish this application. Find the email and enter the code here: the agent types it into the form and submits it.`;
      Object.assign(job, { state: 'handoff', asksForCode: true, reason });
      return fail(502, 'submit_unconfirmed', reason);
    }
    return ok(submitJob(job, 'agent'));
  }),
  http.post(apiPath('/jobs/:id/verification-code'), async ({ params, request }) => {
    const job = findJob(params.id);
    if (!job || job.state !== 'handoff') return notHandoff();
    if (!job.asksForCode) {
      return fail(409, 'no_code_window', 'This job isn’t waiting for an emailed code anymore.');
    }
    const { code } = (await request.json()) as { code?: string };
    const trimmed = (code ?? '').replace(/\s+/g, '');
    if (!trimmed) return fail(422, 'invalid_code', 'Enter the code from the email.');
    // All zeros stands in for a code the site rejects.
    if (/^0+$/.test(trimmed)) {
      return fail(
        422,
        'code_rejected',
        'The site didn’t take that code. Check that it’s from the newest email the site sent, and try again.',
      );
    }
    return ok(submitJob(job, 'agent'));
  }),
  http.post(apiPath('/jobs/:id/mark-submitted'), async ({ params }) => {
    const job = findJob(params.id);
    if (!job || job.state !== 'handoff') return notHandoff();
    return ok(submitJob(job, 'you'));
  }),
];
