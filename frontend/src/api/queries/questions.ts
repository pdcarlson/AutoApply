/** Query hooks for answering a question the agent paused on. */
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { questionsApi } from '@/api/endpoints';
import type { AgentQuestion, AnswerScope, Job } from '@/api/types';
import { useInvalidateWork } from './invalidation';
import { queryKeys } from './keys';

/** Writes a question update into the cached job so the thread re-renders without a refetch. */
function useSetQuestion() {
  const client = useQueryClient();
  return (jobId: string, question: AgentQuestion) =>
    client.setQueryData<Job[]>(queryKeys.jobs, (jobs) =>
      jobs?.map((job) => (job.id === jobId ? { ...job, question } : job)),
    );
}

/** Sends the user's reply; the agent answers with its reading of it. */
export function useReplyToQuestion() {
  const setQuestion = useSetQuestion();
  return useMutation({
    mutationFn: ({ jobId, text }: { jobId: string; text: string }) =>
      questionsApi.reply(jobId, text),
    onSuccess: (question, { jobId }) => setQuestion(jobId, question),
  });
}

/** Picks one of the field's options as the answer. */
export function usePickAnswer() {
  const setQuestion = useSetQuestion();
  return useMutation({
    mutationFn: ({ jobId, value }: { jobId: string; value: string }) =>
      questionsApi.pick(jobId, value),
    onSuccess: (question, { jobId }) => setQuestion(jobId, question),
  });
}

/** Discards the proposed answer so the user can reply again. */
export function useReviseReply() {
  const setQuestion = useSetQuestion();
  return useMutation({
    mutationFn: (jobId: string) => questionsApi.revise(jobId),
    onSuccess: (question, jobId) => setQuestion(jobId, question),
  });
}

/** Accepts the proposed answer, saves it to the Answer bank, and requeues the job. */
export function useAcceptAnswer() {
  const invalidate = useInvalidateWork();
  return useMutation({
    mutationFn: ({ jobId, scope }: { jobId: string; scope: AnswerScope }) =>
      questionsApi.accept(jobId, scope),
    onSuccess: invalidate,
  });
}
