import { useEffect, useState } from 'react';
import { authHeaders, usesAuthTokens } from './authToken';
import { apiUrl } from './client';

/** An API path like `/api/screenshots/x.png`, on the API's origin (which may not be this page's). */
const onApiOrigin = (url: string) => new URL(url, apiUrl('/')).toString();

/**
 * A `src` for an image the API serves. An `<img>` can't send the session token, so with
 * token sign-in the picture is fetched with it and shown from memory; otherwise the URL is
 * used as is. Undefined while loading (or when it couldn't be loaded).
 */
export function useApiImage(url: string | null | undefined): string | undefined {
  const [fetched, setFetched] = useState<{ url: string; src: string }>();
  const viaFetch = usesAuthTokens();

  useEffect(() => {
    if (!url || !viaFetch) return;
    let stopped = false;
    let objectUrl: string | undefined;
    void (async () => {
      try {
        const response = await fetch(onApiOrigin(url), { headers: await authHeaders() });
        if (!response.ok || stopped) return;
        objectUrl = URL.createObjectURL(await response.blob());
        if (stopped) URL.revokeObjectURL(objectUrl);
        else setFetched({ url, src: objectUrl });
      } catch {
        // Left blank; the page around it still works.
      }
    })();
    return () => {
      stopped = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url, viaFetch]);

  if (!url) return undefined;
  if (!viaFetch) return onApiOrigin(url);
  return fetched?.url === url ? fetched.src : undefined;
}
