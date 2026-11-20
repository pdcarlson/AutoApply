/** Query hooks for sent applications and the Answer bank. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { answersApi, applicationsApi } from '@/api/endpoints';
import type { AnswerInput, ApplicationStatus } from '@/api/types';
import { queryKeys } from './keys';

/** Every sent application, newest first. */
export const useApplications = () =>
  useQuery({ queryKey: queryKeys.applications, queryFn: applicationsApi.list });

/** One application with its fields and timeline, or nothing when `id` is null. */
export function useApplication(id: string | null) {
  return useQuery({
    queryKey: queryKeys.application(id ?? ''),
    queryFn: () => applicationsApi.get(id!),
    enabled: id !== null,
  });
}

/** Moves an application to another status, e.g. Interviewing. */
export function useSetApplicationStatus() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: ApplicationStatus }) =>
      applicationsApi.setStatus(id, status),
    onSuccess: (application) =>
      Promise.all([
        client.invalidateQueries({ queryKey: queryKeys.applications }),
        client.invalidateQueries({ queryKey: queryKeys.application(application.id) }),
      ]),
  });
}

/** Every saved answer. */
export const useAnswers = () => useQuery({ queryKey: queryKeys.answers, queryFn: answersApi.list });

/** Adds an answer to the bank. */
export function useCreateAnswer() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: AnswerInput) => answersApi.create(input),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.answers }),
  });
}

/** Edits a saved answer. */
export function useUpdateAnswer() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Partial<AnswerInput> }) =>
      answersApi.update(id, patch),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.answers }),
  });
}

/** Removes a saved answer; the agent asks again next time a form needs it. */
export function useDeleteAnswer() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => answersApi.remove(id),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.answers }),
  });
}
