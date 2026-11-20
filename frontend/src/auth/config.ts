/** Clerk's publishable key. Set: sign in with Google through Clerk. Empty: the local demo sign-in. */
export const clerkKey = (import.meta.env.VITE_CLERK_PUBLISHABLE_KEY ?? '').trim();

export const clerkEnabled = clerkKey !== '';
