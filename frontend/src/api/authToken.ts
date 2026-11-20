/**
 * Where API requests get the signed-in user's token.
 *
 * With Clerk sign-in (VITE_CLERK_PUBLISHABLE_KEY is set) `main.tsx` registers Clerk's
 * `getToken` here, and every request, the live browser socket and screenshots send it. With
 * the local backend or the mock API nothing is registered and requests go out as before.
 */
type TokenSource = () => Promise<string | null>;

let source: TokenSource | null = null;

export function setTokenSource(next: TokenSource | null) {
  source = next;
}

/** True when requests must carry a token (so plain `<img src>` and bare sockets won't do). */
export const usesAuthTokens = () => source !== null;

/** The current session token, or null when signed out or when no sign-in is configured. */
export async function authToken(): Promise<string | null> {
  return source ? source() : null;
}

/** `{ Authorization: 'Bearer …' }` when there is a token, otherwise `{}`. */
export async function authHeaders(): Promise<Record<string, string>> {
  const token = await authToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
