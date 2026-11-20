/** Cache keys for every query, and how often live data is refetched. */

/** How often to refetch while the agent is working, so progress and new states show up. */
export const LIVE_POLL_MS = 2000;

/** The one place query keys are written. */
export const queryKeys = {
  session: ['session'] as const,
  profile: ['profile'] as const,
  resumeParse: ['resume', 'parse'] as const,
  commonAnswers: ['common-answers'] as const,
  preferences: ['preferences'] as const,
  settings: ['settings'] as const,
  agentStatus: ['agent', 'status'] as const,
  jobs: ['jobs'] as const,
  job: (id: string) => ['jobs', id] as const,
  postings: ['postings'] as const,
  applications: ['applications'] as const,
  application: (id: string) => ['applications', id] as const,
  answers: ['answers'] as const,
};
