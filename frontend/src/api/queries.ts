import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  accountApi,
  agentApi,
  answersApi,
  applicationsApi,
  authApi,
  commonAnswersApi,
  jobsApi,
  preferencesApi,
  profileApi,
  questionsApi,
  resumeApi,
} from './endpoints';
import { isApiError } from './client';
import type {
  AgentQuestion,
  AgentSettings,
  AnswerInput,
  AnswerScope,
  ApplicationStatus,
  CommonAnswers,
  Job,
  JobPreferences,
  Profile,
  ProfileUpdate,
} from './types';

/** How often to refetch while the agent is working, so progress and new states show up. */
export const LIVE_POLL_MS = 2000;

export const queryKeys = {
  session: ['session'] as const,
  profile: ['profile'] as const,
  resumeParse: ['resume', 'parse'] as const,
  commonAnswers: ['common-answers'] as const,
  preferences: ['preferences'] as const,
  settings: ['settings'] as const,
  agentStatus: ['agent', 'status'] as const,
  jobs: ['jobs'] as const,
  job: (id: string) => ['jobs', id] as const,
  applications: ['applications'] as const,
  application: (id: string) => ['applications', id] as const,
  answers: ['answers'] as const,
};

const isActive = (job: Job) => job.state === 'queued' || job.state === 'running';

// ===== Session =====

export function useSession() {
  return useQuery({
    queryKey: queryKeys.session,
    queryFn: async () => {
      try {
        return await authApi.getSession();
      } catch (error) {
        if (isApiError(error) && error.status === 401) return null;
        throw error;
      }
    },
    staleTime: 60_000,
  });
}

// ===== Profile & setup =====

export const useProfile = () => useQuery({ queryKey: queryKeys.profile, queryFn: profileApi.get });

export function useUpdateProfile() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (profile: ProfileUpdate) => profileApi.update(profile),
    onSuccess: (profile) => {
      client.setQueryData(queryKeys.profile, profile);
      // The session's display name is built from the profile's name fields.
      void client.invalidateQueries({ queryKey: queryKeys.session });
    },
  });
}

export function useResolveUnplaced() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action }: { id: string; action: 'accept' | 'dismiss' }) =>
      profileApi.resolveUnplaced(id, action),
    onSuccess: (profile) => client.setQueryData(queryKeys.profile, profile),
  });
}

export function useConfirmProfile() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: profileApi.confirm,
    onSuccess: (session) => client.setQueryData(queryKeys.session, session),
  });
}

export function useResumeParse(enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.resumeParse,
    queryFn: async () => {
      try {
        return await resumeApi.getParse();
      } catch (error) {
        if (isApiError(error, 'not_found')) return null;
        throw error;
      }
    },
    enabled,
    refetchInterval: (query) => (query.state.data?.status === 'parsing' ? 1000 : false),
  });
}

export function useUploadResume() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => resumeApi.upload(file),
    onSuccess: (parse) => {
      client.setQueryData(queryKeys.resumeParse, parse);
      // The parse fills the profile; refetch it once parsing finishes or right away.
      void client.invalidateQueries({ queryKey: queryKeys.profile });
    },
  });
}

export function useReplaceResumeFile() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => resumeApi.replaceFile(file),
    onSuccess: (resume) =>
      client.setQueryData<Profile>(queryKeys.profile, (profile) =>
        profile ? { ...profile, resume } : profile,
      ),
  });
}

export const useCommonAnswers = () =>
  useQuery({ queryKey: queryKeys.commonAnswers, queryFn: commonAnswersApi.get });

export function useUpdateCommonAnswers() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (answers: CommonAnswers) => commonAnswersApi.update(answers),
    onSuccess: (answers) => client.setQueryData(queryKeys.commonAnswers, answers),
  });
}

export const usePreferences = () =>
  useQuery({ queryKey: queryKeys.preferences, queryFn: preferencesApi.get });

export function useUpdatePreferences() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (prefs: JobPreferences) => preferencesApi.update(prefs),
    onSuccess: (prefs) => client.setQueryData(queryKeys.preferences, prefs),
  });
}

// ===== Agent =====

export const useAgentSettings = () =>
  useQuery({ queryKey: queryKeys.settings, queryFn: agentApi.getSettings });

export function useUpdateAgentSettings() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (patch: Partial<AgentSettings>) => agentApi.updateSettings(patch),
    onSuccess: (settings) => {
      client.setQueryData(queryKeys.settings, settings);
      // The threshold changes which fields need asking; the limit changes what waits.
      void client.invalidateQueries({ queryKey: queryKeys.jobs });
      void client.invalidateQueries({ queryKey: queryKeys.agentStatus });
    },
  });
}

export function useAgentStatus() {
  return useQuery({
    queryKey: queryKeys.agentStatus,
    queryFn: agentApi.getStatus,
    refetchInterval: (query) => (query.state.data?.queue.length ? LIVE_POLL_MS : false),
  });
}

export function useSetPaused() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (paused: boolean) => (paused ? agentApi.pause() : agentApi.resume()),
    onSuccess: (status) => {
      client.setQueryData(queryKeys.agentStatus, status);
      void client.invalidateQueries({ queryKey: queryKeys.jobs });
    },
  });
}

// ===== Jobs =====

export function useJobs() {
  return useQuery({
    queryKey: queryKeys.jobs,
    queryFn: jobsApi.list,
    refetchInterval: (query) => (query.state.data?.some(isActive) ? LIVE_POLL_MS : false),
  });
}

export function useJob(id: string | null) {
  return useQuery({
    queryKey: queryKeys.job(id ?? ''),
    queryFn: () => jobsApi.get(id!),
    enabled: id !== null,
    refetchInterval: (query) =>
      query.state.data && isActive(query.state.data) ? LIVE_POLL_MS : false,
  });
}

/** Refetches everything a job state change can touch. */
function useInvalidateWork() {
  const client = useQueryClient();
  return () =>
    Promise.all([
      client.invalidateQueries({ queryKey: queryKeys.jobs }),
      client.invalidateQueries({ queryKey: queryKeys.agentStatus }),
      client.invalidateQueries({ queryKey: queryKeys.applications }),
      client.invalidateQueries({ queryKey: queryKeys.answers }),
    ]);
}

export function useAddJob() {
  const invalidate = useInvalidateWork();
  return useMutation({ mutationFn: jobsApi.addFromLink, onSuccess: invalidate });
}

export function useApplyJobs() {
  const invalidate = useInvalidateWork();
  return useMutation({ mutationFn: jobsApi.apply, onSuccess: invalidate });
}

export function useCancelJobs() {
  const invalidate = useInvalidateWork();
  return useMutation({ mutationFn: jobsApi.cancel, onSuccess: invalidate });
}

export function useSkipJob() {
  const invalidate = useInvalidateWork();
  return useMutation({ mutationFn: jobsApi.skip, onSuccess: invalidate });
}

export function useRestoreJob() {
  const invalidate = useInvalidateWork();
  return useMutation({ mutationFn: jobsApi.restore, onSuccess: invalidate });
}

export function useSubmitJob() {
  const invalidate = useInvalidateWork();
  return useMutation({ mutationFn: jobsApi.submit, onSuccess: invalidate });
}

export function useMarkSubmitted() {
  const invalidate = useInvalidateWork();
  return useMutation({ mutationFn: jobsApi.markSubmitted, onSuccess: invalidate });
}

// ===== Agent questions =====

/** Writes a question update into the cached job so the thread re-renders without a refetch. */
function useSetQuestion() {
  const client = useQueryClient();
  return (jobId: string, question: AgentQuestion) =>
    client.setQueryData<Job[]>(queryKeys.jobs, (jobs) =>
      jobs?.map((job) => (job.id === jobId ? { ...job, question } : job)),
    );
}

export function useReplyToQuestion() {
  const setQuestion = useSetQuestion();
  return useMutation({
    mutationFn: ({ jobId, text }: { jobId: string; text: string }) =>
      questionsApi.reply(jobId, text),
    onSuccess: (question, { jobId }) => setQuestion(jobId, question),
  });
}

export function usePickAnswer() {
  const setQuestion = useSetQuestion();
  return useMutation({
    mutationFn: ({ jobId, value }: { jobId: string; value: string }) =>
      questionsApi.pick(jobId, value),
    onSuccess: (question, { jobId }) => setQuestion(jobId, question),
  });
}

export function useReviseReply() {
  const setQuestion = useSetQuestion();
  return useMutation({
    mutationFn: (jobId: string) => questionsApi.revise(jobId),
    onSuccess: (question, jobId) => setQuestion(jobId, question),
  });
}

export function useAcceptAnswer() {
  const invalidate = useInvalidateWork();
  return useMutation({
    mutationFn: ({ jobId, scope }: { jobId: string; scope: AnswerScope }) =>
      questionsApi.accept(jobId, scope),
    onSuccess: invalidate,
  });
}

// ===== Applications =====

export const useApplications = () =>
  useQuery({ queryKey: queryKeys.applications, queryFn: applicationsApi.list });

export function useApplication(id: string | null) {
  return useQuery({
    queryKey: queryKeys.application(id ?? ''),
    queryFn: () => applicationsApi.get(id!),
    enabled: id !== null,
  });
}

export function useSetApplicationStatus() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: ApplicationStatus }) =>
      applicationsApi.setStatus(id, status),
    onSuccess: (app) =>
      Promise.all([
        client.invalidateQueries({ queryKey: queryKeys.applications }),
        client.invalidateQueries({ queryKey: queryKeys.application(app.id) }),
      ]),
  });
}

// ===== Answer bank =====

export const useAnswers = () => useQuery({ queryKey: queryKeys.answers, queryFn: answersApi.list });

export function useCreateAnswer() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: AnswerInput) => answersApi.create(input),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.answers }),
  });
}

export function useUpdateAnswer() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Partial<AnswerInput> }) =>
      answersApi.update(id, patch),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.answers }),
  });
}

export function useDeleteAnswer() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => answersApi.remove(id),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.answers }),
  });
}

// ===== Account =====

export function useSignOut() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: authApi.signOut,
    onSettled: () => {
      client.clear();
      client.setQueryData(queryKeys.session, null);
    },
  });
}

export function useDeleteAccount() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: accountApi.remove,
    onSuccess: () => {
      client.clear();
      client.setQueryData(queryKeys.session, null);
    },
  });
}
