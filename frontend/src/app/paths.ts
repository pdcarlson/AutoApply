/** Every route path in the app, and helpers that link deep into a screen. */

/** The URL path of each screen. */
export const paths = {
  signIn: '/sign-in',
  authCallback: '/auth/callback',
  /** Clerk sign-in only: where Google returns to. */
  ssoCallback: '/sso-callback',
  accountDeleted: '/account-deleted',
  setupResume: '/setup/resume',
  setupProfile: '/setup/profile',
  setupQuestions: '/setup/questions',
  inbox: '/inbox',
  jobs: '/jobs',
  applications: '/applications',
  answers: '/answers',
  profile: '/profile',
  settings: '/settings',
} as const;

/** Inbox with one job expanded and scrolled into view. */
export const inboxJob = (jobId: string) => `${paths.inbox}?job=${encodeURIComponent(jobId)}`;

/** Profile scrolled to one section. */
export const profileSection = (section: string) => `${paths.profile}#${section}`;
