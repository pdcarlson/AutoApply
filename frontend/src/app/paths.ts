export const paths = {
  signIn: '/sign-in',
  authCallback: '/auth/callback',
  accountDeleted: '/account-deleted',
  setupResume: '/setup/resume',
  setupProfile: '/setup/profile',
  setupQuestions: '/setup/questions',
  inbox: '/inbox',
  applications: '/applications',
  answers: '/answers',
  profile: '/profile',
  settings: '/settings',
} as const;

/** Inbox with one job expanded and scrolled into view. */
export const inboxJob = (jobId: string) => `${paths.inbox}?job=${encodeURIComponent(jobId)}`;

/** Profile scrolled to one section. */
export const profileSection = (section: string) => `${paths.profile}#${section}`;
