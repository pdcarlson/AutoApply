/** Builds the app's TanStack Query client and its error and retry rules. */
import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query';
import { isApiError } from '@/api/client';
import { queryKeys } from '@/api/queries/keys';

const STALE_MS = 10_000;
const MAX_RETRIES = 2;

/** Client errors (4xx) won't succeed on retry; network blips and 5xx might. */
const shouldRetry = (failures: number, error: unknown) =>
  failures < MAX_RETRIES && !(isApiError(error) && error.status >= 400 && error.status < 500);

/** A query client that signs the user out on any 401 and retries only what might recover. */
export function createQueryClient() {
  // A 401 from any request means the session ended (expired, or signed out elsewhere).
  // Clearing the cached session makes the route guard send the user to sign in.
  const onError = (error: unknown) => {
    if (isApiError(error) && error.status === 401) client.setQueryData(queryKeys.session, null);
  };

  const client: QueryClient = new QueryClient({
    queryCache: new QueryCache({ onError }),
    mutationCache: new MutationCache({ onError }),
    defaultOptions: {
      queries: { staleTime: STALE_MS, retry: shouldRetry },
    },
  });
  return client;
}
