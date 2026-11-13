# Auto Apply API (frontend contract)

What the frontend calls and expects back. The TypeScript shapes in
[`src/api/types.ts`](../src/api/types.ts) are the source of truth for every body named here, and
[`src/api/endpoints.ts`](../src/api/endpoints.ts) has one function per endpoint.
[`src/mocks/handlers.ts`](../src/mocks/handlers.ts) is a working reference implementation.

## Conventions

- Base path `/api` (configurable with `VITE_API_BASE_URL`). JSON in and out, except uploads
  (`multipart/form-data`, field `file`) and the data export.
- Auth is a session cookie set by the backend. Every request sends it. A missing or expired
  session returns `401 { "code": "unauthenticated" }`.
- Timestamps are ISO 8601 (`2026-10-20T13:41:00Z`); calendar dates are `YYYY-MM-DD`.
- Errors use any 4xx/5xx with this body. `code` is stable and the UI branches on it; `message` may
  be shown to the user.

  ```json
  { "code": "unsupported_site", "message": "…", "details": {} }
  ```

## Auth

| Method | Path           | Body           | Response                               |
| ------ | -------------- | -------------- | -------------------------------------- |
| GET    | `/session`     |                | `200 Session` or `401 unauthenticated` |
| POST   | `/auth/google` | `{ returnTo }` | `200 { authorizationUrl }`             |
| POST   | `/auth/logout` |                | `204`                                  |

Sign-in flow: the frontend POSTs `/auth/google`, sends the browser to `authorizationUrl`, Google
redirects to the backend's own callback, and the backend sets the cookie and redirects to
`/auth/callback?returnTo=<path>`. On cancel or failure redirect to `/auth/callback?error=access_denied`
(or another error code).

## Setup and profile

| Method | Path                    | Body                                | Response                                                       |
| ------ | ----------------------- | ----------------------------------- | -------------------------------------------------------------- |
| POST   | `/resume`               | multipart `file`                    | `202 ResumeParse` (`parsing`); `422 invalid_type \| too_large` |
| GET    | `/resume/parse`         |                                     | `200 ResumeParse`; `404 not_found` before any upload           |
| PUT    | `/resume/file`          | multipart `file`                    | `200 ResumeFile` (swap the file, don't re-parse)               |
| GET    | `/profile`              |                                     | `200 Profile`                                                  |
| PUT    | `/profile`              | `ProfileUpdate`                     | `200 Profile`                                                  |
| POST   | `/profile/unplaced/:id` | `{ action: "accept" \| "dismiss" }` | `200 Profile`                                                  |
| POST   | `/profile/confirm`      |                                     | `200 Session` (`profileConfirmed: true`)                       |
| GET    | `/common-answers`       |                                     | `200 CommonAnswers`                                            |
| PUT    | `/common-answers`       | `CommonAnswers`                     | `200 CommonAnswers`                                            |
| GET    | `/preferences`          |                                     | `200 JobPreferences`                                           |
| PUT    | `/preferences`          | `JobPreferences`                    | `200 JobPreferences`                                           |

The name is three `Profile` fields: `firstName`, `middleName` (optional, `""` when absent), and
`lastName`. Setup requires a first and last name. A parsed resume fills all three from its name line
("Mary Ann Smith" gives `Mary` / `Ann` / `Smith`; every word between the first and the last is the
middle name). `Session.user.name` is the read-only display name built from them. Profiles saved
before the split (a single `name`) are split the same way when the backend loads them.

The frontend polls `/resume/parse` once a second while `status` is `parsing`, showing each entry of
`sections` as it arrives. A finished parse fills the profile; the frontend refetches `/profile`.
`error.code: "unreadable"` offers "Fill it in by hand".

## Agent

| Method | Path            | Body                     | Response            |
| ------ | --------------- | ------------------------ | ------------------- |
| GET    | `/settings`     |                          | `200 AgentSettings` |
| PATCH  | `/settings`     | `Partial<AgentSettings>` | `200 AgentSettings` |
| GET    | `/agent/status` |                          | `200 AgentStatus`   |
| POST   | `/agent/pause`  |                          | `200 AgentStatus`   |
| POST   | `/agent/resume` |                          | `200 AgentStatus`   |

`confidenceThreshold` is 0–100 (default 90); `dailyLimit` is 1–50. `AgentStatus.queue` lists job
ids in the order the agent will work them (running, queued, then waiting).

## Jobs (Inbox)

| Method | Path                       | Body         | Response                                                                                                                                         |
| ------ | -------------------------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| GET    | `/jobs`                    |              | `200 Job[]`: every job not yet submitted or skipped                                                                                              |
| GET    | `/jobs/:id`                |              | `200 JobDetail` (adds `fields`, `currentField`)                                                                                                  |
| POST   | `/jobs`                    | `{ url }`    | `201 Job`; `422 invalid_url \| unsupported_site \| posting_closed`; `409 already_applied \| already_in_inbox` with `AddJobConflict` in `details` |
| POST   | `/jobs/apply`              | `{ jobIds }` | `200 ApplyResult { queued, deferred }`; `409 profile_not_confirmed`                                                                              |
| POST   | `/jobs/cancel`             | `{ jobIds }` | `204` (undo an apply)                                                                                                                            |
| POST   | `/jobs/:id/skip`           |              | `204`                                                                                                                                            |
| POST   | `/jobs/:id/restore`        |              | `200 Job` (undo a skip)                                                                                                                          |
| POST   | `/jobs/:id/submit`         |              | `200 Application` (approve a `ready` job; respond once submitted)                                                                                |
| POST   | `/jobs/:id/mark-submitted` |              | `200 Application` (user finished a `handoff` job themselves)                                                                                     |

Job `state` values and what the UI does with them:

| State         | Meaning                                                                | Shown in                         |
| ------------- | ---------------------------------------------------------------------- | -------------------------------- |
| `open`        | In the Inbox, not approved                                             | Inbox (selectable)               |
| `queued`      | Approved, waiting its turn                                             | Inbox, Applying now              |
| `running`     | Being filled; `phase` is `opening`/`filling`/`submitting`/`confirming` | Inbox, Applying now              |
| `waiting`     | Approved, held until tomorrow by the daily limit                       | Inbox, Applying now              |
| `needs_input` | Paused on `question`                                                   | Inbox, Answer bank banner        |
| `handoff`     | Stopped at a CAPTCHA or login; user finishes on site                   | Inbox                            |
| `ready`       | Filled, waiting for the user's review                                  | Applications ("Ready to submit") |

Only Greenhouse (`*.greenhouse.io`) and Ashby (`*.ashbyhq.com`) links are accepted.

The frontend polls `/jobs` and `/agent/status` every 2 s while any job is `queued` or `running`,
and shows a toast when a job moves to `needs_input`, `handoff`, `ready`, or from `queued` to
`waiting`.

## Agent questions

| Method | Path                          | Body                            | Response                                        |
| ------ | ----------------------------- | ------------------------------- | ----------------------------------------------- |
| POST   | `/jobs/:id/question/messages` | `{ text }`                      | `200 AgentQuestion`                             |
| PUT    | `/jobs/:id/question/answer`   | `{ value }`                     | `200 AgentQuestion` (pick one of `pickOptions`) |
| DELETE | `/jobs/:id/question/answer`   |                                 | `200 AgentQuestion` (clear `proposedAnswer`)    |
| POST   | `/jobs/:id/question/accept`   | `{ scope: "all" \| "company" }` | `200 Job`                                       |

The backend owns the conversation: `messages` starts with the agent's prompt, each user reply is
appended along with any follow-up, and `proposedAnswer` is set once the reply can be used.
`pickOptions` holds every option when the form's field only takes one of a fixed set: the user
picks one (`PUT .../answer`) and the frontend shows no reply box. It is `null` for free-text
fields, which are answered by replying. Accepting saves the answer to the Answer
bank (company-only when `scope` is `company`) and puts the job back at the front of the queue.

## Applications

| Method | Path                | Body         | Response                                                        |
| ------ | ------------------- | ------------ | --------------------------------------------------------------- |
| GET    | `/applications`     |              | `200 Application[]`, newest first                               |
| GET    | `/applications/:id` |              | `200 ApplicationDetail` (`fields`, `timeline`, `screenshotUrl`) |
| PATCH  | `/applications/:id` | `{ status }` | `200 Application`                                               |

`status` is `submitted`, `interviewing`, `offer`, or `rejected`. `screenshotUrl` must be loadable
by an `<img>` from the app (same origin, or a signed URL); it's null when the user submitted the
form themselves. Timeline events of kind `current` show elapsed time since `at`.

## Answer bank

| Method | Path           | Body                   | Response       |
| ------ | -------------- | ---------------------- | -------------- |
| GET    | `/answers`     |                        | `200 Answer[]` |
| POST   | `/answers`     | `AnswerInput`          | `201 Answer`   |
| PATCH  | `/answers/:id` | `Partial<AnswerInput>` | `200 Answer`   |
| DELETE | `/answers/:id` |                        | `204`          |

## Account

| Method | Path              | Response                                                         |
| ------ | ----------------- | ---------------------------------------------------------------- |
| GET    | `/account/export` | `200` file, with `Content-Disposition: attachment; filename="…"` |
| DELETE | `/account`        | `204`; also ends the session                                     |
