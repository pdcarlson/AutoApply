# AutoApply

AutoApply fills in job applications for you. You upload a resume and answer a few setup
questions; the agent then opens Greenhouse and Ashby job forms in a browser, fills them, asks you
about anything it can't answer, and waits for your review before it submits.

## Repo layout

| Folder                | What it holds                                                                  |
| --------------------- | ------------------------------------------------------------------------------ |
| `backend/agent/`      | The agent: reads job forms, drafts answers, drives the browser with Playwright |
| `backend/server/`     | The FastAPI web API, per-user storage and the job queue                        |
| `backend/onboarding/` | Answer bank, onboarding questions and resume reading, used by the server       |
| `frontend/`           | The React + TypeScript web app (see [frontend/README.md](frontend/README.md))  |

## Run the web app

The backend runs on Fly.io at https://autoapply-api-b97199.fly.dev. There is no hosted frontend;
you run it on your machine against that API. You need Node 20+.

1. From `frontend/`, run `npm install`.
2. Copy `frontend/.env.example` to `frontend/.env.local` and fill in:

   ```
   VITE_API_BASE_URL=https://autoapply-api-b97199.fly.dev/api
   VITE_CLERK_PUBLISHABLE_KEY=pk_...
   ```

3. Run `npm run dev` and open http://localhost:5173 (it must be listed in the backend's
   `ALLOWED_ORIGINS`), or run `npm run build` for a production build in `frontend/dist/`.

Sign in with Google, upload your resume, check your profile and answer the setup questions. Then
paste a job link into the Inbox, or press **Apply** on a posting under **Jobs**.

## Deploy the backend

The API, the agent and its browser run together in one container, built from
`backend/Dockerfile` and configured by `backend/fly.toml`. People sign in through
[Clerk](https://clerk.com); create a Clerk application with Google sign-in and copy its
publishable (`pk_...`) and secret (`sk_...`) keys.

With [flyctl](https://fly.io/docs/flyctl/) signed in, from `backend/`:

```powershell
fly secrets set CLERK_PUBLISHABLE_KEY=pk_... CLERK_SECRET_KEY=sk_... ALLOWED_ORIGINS=http://localhost:5173
fly deploy
```

`https://autoapply-api-b97199.fly.dev/api/health` answers `{"ok": true, ...}` once it is up.

After that, every change to `backend/` on `main` deploys itself:
`.github/workflows/deploy-backend.yml` runs the backend tests and, if they pass, runs
`fly deploy`. It needs a repository secret `FLY_API_TOKEN` holding a token from
`fly tokens create deploy`. To redeploy by hand, run it from the repo's **Actions** tab.

To run the same server somewhere else, install the dependencies (see [Run the tests](#run-the-tests)),
set the environment variables below, and run `python -m server` from `backend/`. It listens on
`127.0.0.1:8080` unless `AUTOAPPLY_HOST` and `AUTOAPPLY_PORT` say otherwise.

How it runs on Fly:

- **One machine, stopped when idle.** Fly stops the machine a few minutes after the last request
  and starts it again on the next one, so the first request after a pause is slower. Stopping or
  redeploying closes open browsers: a form waiting for review is filled again at Submit, and
  queued jobs wait until the machine starts. For always-on, set `auto_stop_machines = "off"` and
  `min_machines_running = 1` in `fly.toml`. Never scale to more than one machine: a filled form
  is an open browser inside one server process.
- **Data** lives on the volume mounted at `/data`, in one folder per Clerk user. **Delete
  account** removes that folder and the person's Clerk user.
- **Nobody sees the server's browser**, so the live view in the web app is the way to reach a
  form yourself (for a CAPTCHA, say).

## Environment variables

Set them with `fly secrets set NAME=value` (or in `backend/fly.toml` under `[env]`), or in the
environment when running `python -m server`.

| Variable                | Required | What it does                                                                   |
| ----------------------- | -------- | ------------------------------------------------------------------------------ |
| `CLERK_PUBLISHABLE_KEY` | Yes\*    | Which Clerk application's sign-ins are accepted. \*Or set `CLERK_ISSUER`.      |
| `CLERK_SECRET_KEY`      | Yes      | Reads a new user's name and email; deletes the Clerk user on Delete account.   |
| `ALLOWED_ORIGINS`       | Yes      | Comma-separated web app addresses allowed to call the API.                     |
| `ANTHROPIC_API_KEY`     | No       | With a key, Claude drafts answers. Without one, the agent asks the user.       |
| `SUBMIT_REAL_FORM`      | No       | `false` (default): Submit records the application but never sends it.          |
| `AUTOAPPLY_DATA_DIR`    | No       | Where user data is kept. Default `backend/data` (`/data` on Fly).              |
| `MAX_CONCURRENT_RUNS`   | No       | How many browsers may fill or submit at once, across all users. Default `2`.   |
| `CONFIRM_TIMEOUT_S`     | No       | How long Submit waits for the thank-you page. Default `90`.                    |
| `BROWSER_CDP_URL`       | No       | DevTools address of a Chromium running elsewhere, used instead of a local one. |

## Run the tests

Backend, from `backend/` (Python 3.11+):

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r server/requirements.txt
.venv\Scripts\python -m playwright install chromium
.venv\Scripts\python -m pytest
```

Frontend, from `frontend/`: `npm test`. It needs no `.env` file.

## API

All paths are under `/api`. Requests and responses are JSON, except uploads (`multipart/form-data`,
field `file`), the data export and screenshots. The TypeScript shapes in
`frontend/src/api/types.ts` describe every body, and `frontend/src/api/endpoints.ts` has one
function per endpoint.

**Auth.** Every route except `/health` needs a Clerk session token as
`Authorization: Bearer <token>`; the token's user is whose data the request reads and writes. The
live view socket can't send headers, so it passes the token as a subprotocol:
`["autoapply.live", <token>]`. Screenshots need the token too, so fetch them rather than using an
`<img src>`.

**Errors.** Every 4xx/5xx response has the body below. `code` is stable and the UI branches on
it; `message` may be shown to the user. A request without a valid token gets
`401 unauthenticated`.

```json
{ "code": "unsupported_site", "message": "…", "details": {} }
```

**Session and setup**

- `GET /health`: server is up, with its `submitRealForm` and `claude` switches (no auth)
- `GET /session`: the signed-in user and whether their profile is confirmed
- `POST /resume`: upload a resume and start parsing it (`202`)
- `GET /resume/parse`: parse progress; poll while `status` is `parsing`
- `PUT /resume/file`: replace the resume file without re-parsing
- `GET /profile`, `PUT /profile`: read or save the profile
- `POST /profile/unplaced/:id`: accept or dismiss a resume section that wasn't placed
- `POST /profile/confirm`: finish setup
- `GET /common-answers`, `PUT /common-answers`: the setup questions' answers
- `GET /preferences`, `PUT /preferences`: job preferences used to rank postings

**Agent**

- `GET /settings`, `PATCH /settings`: confidence threshold (0–100) and daily limit (1–50)
- `GET /agent/status`: paused or running, and the queue in work order
- `POST /agent/pause`, `POST /agent/resume`: stop or restart new jobs

**Jobs**

- `GET /jobs`: every job not yet submitted or skipped
- `GET /jobs/:id`: one job with its fields
- `POST /jobs`: add a Greenhouse or Ashby link (`409` if already applied or in the Inbox)
- `POST /jobs/apply`, `POST /jobs/cancel`: queue jobs, or undo that
- `POST /jobs/:id/skip`, `POST /jobs/:id/restore`: skip a job, or undo that
- `POST /jobs/:id/submit`: submit a filled (`ready`) job; `409 protected_step` for CAPTCHAs,
  sign-ins and similar steps the user must do
- `POST /jobs/:id/verification-code`: pass on a code the site emailed to the user
- `POST /jobs/:id/mark-submitted`: the user finished a `handoff` job themselves
- `WS /jobs/:id/live`: live JPEG frames of the job's browser; the client sends mouse, wheel, key
  and text messages back

**Agent questions**

- `POST /jobs/:id/question/messages`: reply to the agent's question
- `PUT /jobs/:id/question/answer`, `DELETE /jobs/:id/question/answer`: pick an option, or clear
  the proposed answer
- `POST /jobs/:id/question/accept`: save the answer to the Answer bank and requeue the job

**Job board**

- `GET /postings`: open postings ranked by fit against the profile
- `POST /postings/:id/apply`: add a posting to the Inbox and queue it

**Applications**

- `GET /applications`: submitted applications, newest first
- `GET /applications/:id`: one application with fields, timeline and `screenshotUrl`
- `PATCH /applications/:id`: set `status` (`submitted`, `interviewing`, `offer`, `rejected`)
- `GET /screenshots/:name`: a confirmation screenshot (PNG)

**Answer bank**

- `GET /answers`, `POST /answers`: list or add saved answers
- `PATCH /answers/:id`, `DELETE /answers/:id`: edit or remove one

**Account**

- `GET /account/export`: download all the user's data as a file
- `DELETE /account`: delete the user's data and their Clerk user (`204`)
