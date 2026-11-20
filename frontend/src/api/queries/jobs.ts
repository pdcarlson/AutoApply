/** Query hooks for Inbox jobs and the job board. */
import { useMutation, useQuery } from '@tanstack/react-query';
import { jobsApi, postingsApi } from '@/api/endpoints';
import type { Job, PostingApplyResult } from '@/api/types';
import { useInvalidateWork } from './invalidation';
import { LIVE_POLL_MS, queryKeys } from './keys';

const isActive = (job: Job) => job.state === 'queued' || job.state === 'running';

/** Every job not yet submitted or skipped; polled while one is being worked on. */
export function useJobs() {
  return useQuery({
    queryKey: queryKeys.jobs,
    queryFn: jobsApi.list,
    refetchInterval: (query) => (query.state.data?.some(isActive) ? LIVE_POLL_MS : false),
  });
}

/** One job with its filled fields, or nothing when `id` is null. */
export function useJob(id: string | null) {
  return useQuery({
    queryKey: queryKeys.job(id ?? ''),
    queryFn: () => jobsApi.get(id!),
    enabled: id !== null,
    refetchInterval: (query) =>
      query.state.data && isActive(query.state.data) ? LIVE_POLL_MS : false,
  });
}

/** Adds a job from a pasted link. */
export function useAddJob() {
  const invalidate = useInvalidateWork();
  return useMutation({ mutationFn: jobsApi.addFromLink, onSuccess: invalidate });
}

/** Approves jobs so the agent applies to them. */
export function useApplyJobs() {
  const invalidate = useInvalidateWork();
  return useMutation({ mutationFn: jobsApi.apply, onSuccess: invalidate });
}

/** Takes approved jobs back out of the queue. */
export function useCancelJobs() {
  const invalidate = useInvalidateWork();
  return useMutation({ mutationFn: jobsApi.cancel, onSuccess: invalidate });
}

/** Hides a job for good. */
export function useSkipJob() {
  const invalidate = useInvalidateWork();
  return useMutation({ mutationFn: jobsApi.skip, onSuccess: invalidate });
}

/** Undoes a skip. */
export function useRestoreJob() {
  const invalidate = useInvalidateWork();
  return useMutation({ mutationFn: jobsApi.restore, onSuccess: invalidate });
}

/** Submits a reviewed job. */
export function useSubmitJob() {
  const invalidate = useInvalidateWork();
  // A failed submit can still move the job (e.g. to `handoff` when the site emails a code).
  return useMutation({ mutationFn: jobsApi.submit, onSettled: invalidate });
}

/** Sends the code the site emailed; the agent types it into the open form and submits. */
export function useEnterCode() {
  const invalidate = useInvalidateWork();
  return useMutation({
    mutationFn: ({ jobId, code }: { jobId: string; code: string }) =>
      jobsApi.enterCode(jobId, code),
    onSettled: invalidate,
  });
}

/** Records that the user finished a handed-off job on the employer's site. */
export function useMarkSubmitted() {
  const invalidate = useInvalidateWork();
  return useMutation({ mutationFn: jobsApi.markSubmitted, onSuccess: invalidate });
}

/** Open postings ranked by fit; polled while the backend is still collecting them. */
export function usePostings() {
  return useQuery({
    queryKey: queryKeys.postings,
    queryFn: postingsApi.list,
    refetchInterval: (query) => (query.state.data?.refreshing ? LIVE_POLL_MS : false),
  });
}

/** Applies to postings one after another. A posting that can't be added doesn't stop the rest. */
export function useApplyToPostings() {
  const invalidate = useInvalidateWork();
  return useMutation({
    mutationFn: async (ids: string[]) => {
      const started: PostingApplyResult[] = [];
      const failed: string[] = [];
      for (const id of ids) {
        try {
          started.push(await postingsApi.apply(id));
        } catch (error) {
          failed.push(error instanceof Error ? error.message : 'It couldn’t be added.');
        }
      }
      return { started, failed };
    },
    onSuccess: invalidate,
  });
}
