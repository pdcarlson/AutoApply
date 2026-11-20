/** Where API requests get the signed-in user's token. */

/** Returns a fresh session token, or null when signed out. */
type TokenSource = () => Promise<string | null>;

let source: TokenSource | null = null;

/** Registers where tokens come from: `main.tsx` registers Clerk's `getToken`. */
export function setTokenSource(next: TokenSource | null) {
  source = next;
}

/** The current session token, or null when signed out or nothing is registered (tests). */
export async function authToken(): Promise<string | null> {
  return source ? source() : null;
}

/** `{ Authorization: 'Bearer …' }` when there is a token, otherwise `{}`. */
export async function authHeaders(): Promise<Record<string, string>> {
  const token = await authToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
