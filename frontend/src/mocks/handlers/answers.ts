/** Mock handlers for the Answer bank. */
import { http } from 'msw';
import type { Answer, AnswerInput } from '@/api/types';
import { db } from '@/mocks/db';
import { apiPath, latency, notFound, ok } from './respond';

/** Listing, adding, editing, and removing saved answers. */
export const answerBankHandlers = [
  http.get(apiPath('/answers'), async () => {
    await latency();
    return ok(db.answers);
  }),
  http.post(apiPath('/answers'), async ({ request }) => {
    await latency();
    const input = (await request.json()) as AnswerInput;
    const answer: Answer = {
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
  http.patch(apiPath('/answers/:id'), async ({ params, request }) => {
    await latency();
    const answer = db.answers.find((candidate) => candidate.id === params.id);
    if (!answer) return notFound('Answer');
    Object.assign(answer, (await request.json()) as Partial<AnswerInput>);
    return ok(answer);
  }),
  http.delete(apiPath('/answers/:id'), async ({ params }) => {
    db.answers = db.answers.filter((answer) => answer.id !== params.id);
    return ok();
  }),
];
