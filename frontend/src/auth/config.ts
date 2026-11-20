/** Clerk sign-in configuration, read from the environment. */

/** Clerk's publishable key. The app shows an error instead of starting when it is missing. */
export const clerkKey = (import.meta.env.VITE_CLERK_PUBLISHABLE_KEY ?? '').trim();
