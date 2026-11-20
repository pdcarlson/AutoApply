/** Mock handlers for the conversation about a question the agent paused on. */
import { http } from 'msw';
import type { AnswerScope } from '@/api/types';
import { acceptAnswer } from '@/mocks/agent';
import { db } from '@/mocks/db';
import { interpretReply } from '@/mocks/replies';
import { toJob } from '@/mocks/wire';
import { apiPath, fail, findJob, latency, notFound, ok } from './respond';

/** Replying to, answering, and accepting a paused question. */
export const questionHandlers = [
  http.post(apiPath('/jobs/:id/question/messages'), async ({ params, request }) => {
    await latency();
    const job = findJob(params.id);
    if (!job?.question) return notFound('Question');
    const { text } = (await request.json()) as { text: string };
    interpretReply(job.question, text);
    return ok(job.question);
  }),
  http.put(apiPath('/jobs/:id/question/answer'), async ({ params, request }) => {
    const job = findJob(params.id);
    if (!job?.question) return notFound('Question');
    const { value } = (await request.json()) as { value: string };
    job.question.proposedAnswer = { value, confidence: 100 };
    return ok(job.question);
  }),
  http.delete(apiPath('/jobs/:id/question/answer'), async ({ params }) => {
    const job = findJob(params.id);
    if (!job?.question) return notFound('Question');
    job.question.proposedAnswer = null;
    return ok(job.question);
  }),
  http.post(apiPath('/jobs/:id/question/accept'), async ({ params, request }) => {
    await latency();
    const job = findJob(params.id);
    if (!job?.question?.proposedAnswer) {
      return fail(409, 'no_answer', 'There’s no answer to use yet.');
    }
    const { scope } = (await request.json()) as { scope: AnswerScope };
    acceptAnswer(job, scope);
    db.lastTick = Date.now();
    return ok(toJob(job));
  }),
];
