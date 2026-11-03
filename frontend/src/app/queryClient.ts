import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query';
import { isApiError } from '@/api/client';
import { queryKeys } from '@/api/queries';

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
      queries: {
        staleTime: 10_000,
        // Client errors (4xx) won't succeed on retry; network blips and 5xx might.
        retry: (failures, error) =>
          failures < 2 && !(isApiError(error) && error.status >= 400 && error.status < 500),
      },
    },
  });
  return client;
}
