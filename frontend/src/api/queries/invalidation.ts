/** The cache refresh that follows any change to a job's state. */
import { useQueryClient } from '@tanstack/react-query';
import { queryKeys } from './keys';

/** Refetches everything a job state change can touch. */
export function useInvalidateWork() {
  const client = useQueryClient();
  return () =>
    Promise.all([
      client.invalidateQueries({ queryKey: queryKeys.jobs }),
      client.invalidateQueries({ queryKey: queryKeys.agentStatus }),
      client.invalidateQueries({ queryKey: queryKeys.applications }),
      client.invalidateQueries({ queryKey: queryKeys.answers }),
      client.invalidateQueries({ queryKey: queryKeys.postings }),
    ]);
}
