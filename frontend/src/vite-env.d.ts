/** Types for Vite and the environment variables the app reads. */
/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base path or URL of the backend API, e.g. `/api` or `https://api.example.com/api`. */
  readonly VITE_API_BASE_URL?: string;
  /** Clerk's publishable key, for Google sign-in through Clerk. */
  readonly VITE_CLERK_PUBLISHABLE_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
