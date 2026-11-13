/**
 * One function per backend endpoint. Paths are relative to VITE_API_BASE_URL (default `/api`).
 * All requests send the session cookie; any non-2xx response throws an ApiError carrying the
 * `{ code, message, details }` body. docs/api.md lists the same endpoints for the backend team.
 */
import { http } from './client';
import type {
  AgentQuestion,
  AgentSettings,
  AgentStatus,
  Answer,
  AnswerInput,
  AnswerScope,
  Application,
  ApplicationDetail,
  ApplicationStatus,
  ApplyResult,
  CommonAnswers,
  GoogleSignInStart,
  Job,
  JobDetail,
  JobPreferences,
  Profile,
  ProfileUpdate,
  ResumeFile,
  ResumeParse,
  Session,
} from './types';

export const authApi = {
  /** GET /session → 200 Session, or 401 `unauthenticated` when signed out. */
  getSession: () => http.get<Session>('/session'),
  /**
   * POST /auth/google { returnTo } → 200 { authorizationUrl }.
   * The backend creates the OAuth state, the browser goes to Google, Google returns to the
   * backend's callback, and the backend sets the session cookie and redirects to
   * `/auth/callback` (or `/auth/callback?error=access_denied` when the user cancels).
   */
  startGoogleSignIn: (returnTo: string) =>
    http.post<GoogleSignInStart>('/auth/google', { returnTo }),
  /** POST /auth/logout → 204. */
  signOut: () => http.post<void>('/auth/logout'),
};

export const profileApi = {
  /** GET /profile → 200 Profile. */
  get: () => http.get<Profile>('/profile'),
  /** PUT /profile ProfileUpdate → 200 Profile. */
  update: (profile: ProfileUpdate) => http.put<Profile>('/profile', profile),
  /** POST /profile/unplaced/:id { action } → 200 Profile. `accept` applies its suggestion. */
  resolveUnplaced: (id: string, action: 'accept' | 'dismiss') =>
    http.post<Profile>(`/profile/unplaced/${id}`, { action }),
  /** POST /profile/confirm → 200 Session. Ends setup; applications may use the profile. */
  confirm: () => http.post<Session>('/profile/confirm'),
};

export const resumeApi = {
  /**
   * POST /resume multipart `file` → 202 ResumeParse (status `parsing`).
   * 422 `invalid_type` | `too_large` when the file is rejected. Replaces any existing resume.
   */
  upload: (file: File) => {
    const form = new FormData();
    form.append('file', file, file.name);
    return http.post<ResumeParse>('/resume', form);
  },
  /** GET /resume/parse → 200 ResumeParse for the latest upload; 404 `not_found` if none. */
  getParse: () => http.get<ResumeParse>('/resume/parse'),
  /**
   * PUT /resume/file multipart `file` → 200 ResumeFile. Swaps the attached file without
   * re-reading it into the profile. Applications already sent keep the old file.
   */
  replaceFile: (file: File) => {
    const form = new FormData();
    form.append('file', file, file.name);
    return http.put<ResumeFile>('/resume/file', form);
  },
};

export const commonAnswersApi = {
  /** GET /common-answers → 200 CommonAnswers. */
  get: () => http.get<CommonAnswers>('/common-answers'),
  /** PUT /common-answers CommonAnswers → 200 CommonAnswers. */
  update: (answers: CommonAnswers) => http.put<CommonAnswers>('/common-answers', answers),
};

export const preferencesApi = {
  /** GET /preferences → 200 JobPreferences. */
  get: () => http.get<JobPreferences>('/preferences'),
  /** PUT /preferences JobPreferences → 200 JobPreferences. */
  update: (prefs: JobPreferences) => http.put<JobPreferences>('/preferences', prefs),
};

export const agentApi = {
  /** GET /settings → 200 AgentSettings. */
  getSettings: () => http.get<AgentSettings>('/settings'),
  /** PATCH /settings Partial<AgentSettings> → 200 AgentSettings. */
  updateSettings: (patch: Partial<AgentSettings>) => http.patch<AgentSettings>('/settings', patch),
  /** GET /agent/status → 200 AgentStatus. */
  getStatus: () => http.get<AgentStatus>('/agent/status'),
  /** POST /agent/pause → 200 AgentStatus. The form in progress finishes; nothing new starts. */
  pause: () => http.post<AgentStatus>('/agent/pause'),
  /** POST /agent/resume → 200 AgentStatus. */
  resume: () => http.post<AgentStatus>('/agent/resume'),
};

export const jobsApi = {
  /** GET /jobs → 200 Job[]: every job not yet submitted or skipped (Inbox, queue, ready). */
  list: () => http.get<Job[]>('/jobs'),
  /** GET /jobs/:id → 200 JobDetail, including the fields filled so far. */
  get: (id: string) => http.get<JobDetail>(`/jobs/${id}`),
  /**
   * POST /jobs { url } → 201 Job.
   * 422 `invalid_url` | `unsupported_site` | `posting_closed`;
   * 409 `already_applied` | `already_in_inbox` with AddJobConflict in `details`.
   */
  addFromLink: (url: string) => http.post<Job>('/jobs', { url }),
  /** POST /jobs/apply { jobIds } → 200 ApplyResult. 409 `profile_not_confirmed`. */
  apply: (jobIds: string[]) => http.post<ApplyResult>('/jobs/apply', { jobIds }),
  /** POST /jobs/cancel { jobIds } → 204. Takes approved jobs back out of the queue (undo). */
  cancel: (jobIds: string[]) => http.post<void>('/jobs/cancel', { jobIds }),
  /** POST /jobs/:id/skip → 204. Hidden for good, even after the next refresh. */
  skip: (id: string) => http.post<void>(`/jobs/${id}/skip`),
  /** POST /jobs/:id/restore → 200 Job. Undoes a skip. */
  restore: (id: string) => http.post<Job>(`/jobs/${id}/restore`),
  /** POST /jobs/:id/submit → 200 Application. Approves a `ready` job; resolves once confirmed. */
  submit: (id: string) => http.post<Application>(`/jobs/${id}/submit`),
  /** POST /jobs/:id/mark-submitted → 200 Application. The user finished a `handoff` job. */
  markSubmitted: (id: string) => http.post<Application>(`/jobs/${id}/mark-submitted`),
  /**
   * POST /extension/jobs/:id/submitted → 200 Application. The user submitted it in their own
   * browser (a Lever job, say), from any state it waits in, not only `handoff`.
   */
  submittedInBrowser: (id: string) => http.post<Application>(`/extension/jobs/${id}/submitted`),
};

export const questionsApi = {
  /** POST /jobs/:id/question/messages { text } → 200 AgentQuestion with the agent's reading. */
  reply: (jobId: string, text: string) =>
    http.post<AgentQuestion>(`/jobs/${jobId}/question/messages`, { text }),
  /** PUT /jobs/:id/question/answer { value } → 200 AgentQuestion. Picks one of pickOptions. */
  pick: (jobId: string, value: string) =>
    http.put<AgentQuestion>(`/jobs/${jobId}/question/answer`, { value }),
  /** DELETE /jobs/:id/question/answer → 200 AgentQuestion. Discards the proposed answer. */
  revise: (jobId: string) => http.delete<AgentQuestion>(`/jobs/${jobId}/question/answer`),
  /**
   * POST /jobs/:id/question/accept { scope } → 200 Job.
   * Saves the answer to the Answer bank and puts the job back at the front of the queue.
   */
  accept: (jobId: string, scope: AnswerScope) =>
    http.post<Job>(`/jobs/${jobId}/question/accept`, { scope }),
};

export const applicationsApi = {
  /** GET /applications → 200 Application[], newest first. */
  list: () => http.get<Application[]>('/applications'),
  /** GET /applications/:id → 200 ApplicationDetail. */
  get: (id: string) => http.get<ApplicationDetail>(`/applications/${id}`),
  /** PATCH /applications/:id { status } → 200 Application. */
  setStatus: (id: string, status: ApplicationStatus) =>
    http.patch<Application>(`/applications/${id}`, { status }),
};

export const answersApi = {
  /** GET /answers → 200 Answer[]. */
  list: () => http.get<Answer[]>('/answers'),
  /** POST /answers AnswerInput → 201 Answer. */
  create: (input: AnswerInput) => http.post<Answer>('/answers', { ...input }),
  /** PATCH /answers/:id Partial<AnswerInput> → 200 Answer. */
  update: (id: string, patch: Partial<AnswerInput>) => http.patch<Answer>(`/answers/${id}`, patch),
  /** DELETE /answers/:id → 204. The agent asks again the next time a form needs it. */
  remove: (id: string) => http.delete(`/answers/${id}`),
};

export const accountApi = {
  /** GET /account/export → 200 file (JSON or ZIP) with the profile, answers, and applications. */
  exportData: () => http.download('/account/export', 'auto-apply-export.json'),
  /** DELETE /account → 204. Removes everything and ends the session. */
  remove: () => http.delete('/account'),
};
