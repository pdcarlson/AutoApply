/** Query hooks for setup data: the profile, the resume, common questions, and preferences. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { isApiError } from '@/api/client';
import { commonAnswersApi, preferencesApi, profileApi, resumeApi } from '@/api/endpoints';
import type { CommonAnswers, JobPreferences, Profile, ProfileUpdate } from '@/api/types';
import { queryKeys } from './keys';

const PARSE_POLL_MS = 1000;

/** The user's profile. */
export const useProfile = () => useQuery({ queryKey: queryKeys.profile, queryFn: profileApi.get });

/** Saves the profile. */
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

/** Accepts or dismisses a piece of resume text the parser couldn't place. */
export function useResolveUnplaced() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action }: { id: string; action: 'accept' | 'dismiss' }) =>
      profileApi.resolveUnplaced(id, action),
    onSuccess: (profile) => client.setQueryData(queryKeys.profile, profile),
  });
}

/** Confirms the profile, which finishes setup. */
export function useConfirmProfile() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: profileApi.confirm,
    onSuccess: (session) => client.setQueryData(queryKeys.session, session),
  });
}

/** The latest resume parse (null if none), polled while it is still parsing. */
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
    refetchInterval: (query) => (query.state.data?.status === 'parsing' ? PARSE_POLL_MS : false),
  });
}

/** Uploads a resume and starts parsing it into the profile. */
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

/** Swaps the attached resume file without re-reading it into the profile. */
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

/** Answers to the common application questions. */
export const useCommonAnswers = () =>
  useQuery({ queryKey: queryKeys.commonAnswers, queryFn: commonAnswersApi.get });

/** Saves the common answers. */
export function useUpdateCommonAnswers() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (answers: CommonAnswers) => commonAnswersApi.update(answers),
    onSuccess: (answers) => client.setQueryData(queryKeys.commonAnswers, answers),
  });
}

/** The kinds of jobs the user wants. */
export const usePreferences = () =>
  useQuery({ queryKey: queryKeys.preferences, queryFn: preferencesApi.get });

/** Saves the job preferences. */
export function useUpdatePreferences() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (preferences: JobPreferences) => preferencesApi.update(preferences),
    onSuccess: (preferences) => client.setQueryData(queryKeys.preferences, preferences),
  });
}
