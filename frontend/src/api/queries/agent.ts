/** Query hooks for the agent's settings and status. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { agentApi } from '@/api/endpoints';
import type { AgentSettings } from '@/api/types';
import { LIVE_POLL_MS, queryKeys } from './keys';

/** The confidence threshold and daily limit. */
export const useAgentSettings = () =>
  useQuery({ queryKey: queryKeys.settings, queryFn: agentApi.getSettings });

/** Changes some of the agent's settings. */
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

/** Whether the agent is paused, what it sent today, and its queue; polled while it has work. */
export function useAgentStatus() {
  return useQuery({
    queryKey: queryKeys.agentStatus,
    queryFn: agentApi.getStatus,
    refetchInterval: (query) => (query.state.data?.queue.length ? LIVE_POLL_MS : false),
  });
}

/** Pauses (true) or resumes (false) the agent. */
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
