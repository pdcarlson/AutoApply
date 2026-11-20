/** Clerk sign-in configuration, read from the environment. */

/** Clerk's publishable key. Set: sign in with Google through Clerk. Empty: the local demo sign-in. */
export const clerkKey = (import.meta.env.VITE_CLERK_PUBLISHABLE_KEY ?? '').trim();

/** True when the app signs in through Clerk. */
export const clerkEnabled = clerkKey !== '';
