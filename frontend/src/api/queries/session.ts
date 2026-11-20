/** Query hooks for the signed-in session and the account: sign-out, export, and deletion. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback } from 'react';
import { useAuthActions } from '@/auth/actions';
import { isApiError } from '@/api/client';
import { accountApi, authApi } from '@/api/endpoints';
import { queryKeys } from './keys';

const SESSION_STALE_MS = 60_000;

/** The current session, or null when signed out. */
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
    staleTime: SESSION_STALE_MS,
  });
}

/**
 * A function that loads the session from the server right now, skipping the cache. Unlike
 * `useSession` it rejects when signed out, so the caller can tell a failed sign-in apart.
 */
export function useFetchFreshSession() {
  const client = useQueryClient();
  return useCallback(
    () =>
      client.fetchQuery({ queryKey: queryKeys.session, queryFn: authApi.getSession, staleTime: 0 }),
    [client],
  );
}

/** Downloads a file with the user's profile, answers, and applications. */
export function useExportData(onError?: () => void) {
  return useMutation({ mutationFn: accountApi.exportData, onError });
}

/** Signs out and forgets every cached answer from the server. */
export function useSignOut() {
  const client = useQueryClient();
  const auth = useAuthActions();
  return useMutation({
    mutationFn: () => auth.signOut(),
    onSettled: () => {
      client.clear();
      client.setQueryData(queryKeys.session, null);
    },
  });
}

/** Deletes the account and everything in it, then clears the cache. */
export function useDeleteAccount() {
  const client = useQueryClient();
  const auth = useAuthActions();
  return useMutation({
    mutationFn: async () => {
      await accountApi.remove();
      // The account is gone either way; a failure here only leaves a stale sign-in behind.
      await auth.afterAccountDeleted().catch(() => undefined);
    },
    onSuccess: () => {
      client.clear();
      client.setQueryData(queryKeys.session, null);
    },
  });
}
