/** Where API requests get the signed-in user's token. */

/** Returns a fresh session token, or null when signed out. */
type TokenSource = () => Promise<string | null>;

let source: TokenSource | null = null;

/**
 * Registers where tokens come from. With Clerk sign-in, `main.tsx` registers Clerk's
 * `getToken`; with the local backend or the mock API nothing is registered.
 */
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
