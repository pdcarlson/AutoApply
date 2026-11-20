/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base path or URL of the backend API, e.g. `/api` or `https://api.example.com`. */
  readonly VITE_API_BASE_URL?: string;
  /** Clerk's publishable key. Set: Google sign-in through Clerk. Unset: the local demo sign-in. */
  readonly VITE_CLERK_PUBLISHABLE_KEY?: string;
  /** `enabled` serves /api from the in-browser mock API (development only). */
  readonly VITE_API_MOCKING?: 'enabled' | 'disabled';
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
