# AutoApply

## Run it locally

You need Python 3.11+ and Node 20+. Commands are for Windows PowerShell.

1. Set up the backend (once), from `backend/`:

   ```powershell
   python -m venv .venv
   .venv\Scripts\python -m pip install -r server/requirements.txt
   .venv\Scripts\python -m playwright install chromium
   copy agent\.env.example agent\.env
   ```

2. Set up the frontend (once), from `frontend/`:

   ```powershell
   npm install
   ```

3. Start it, from the repo root:

   ```powershell
   .\scripts\demo.ps1
   ```

4. Open http://localhost:5173, sign in, upload your resume, check your profile, and answer the
   setup questions.
5. Paste a Greenhouse or Ashby job link into the Inbox and press **Apply**, or open **Jobs** and press
   **Apply** on a posting there. Answer any questions the agent asks, then review the filled form and
   press **Submit**.

Press Ctrl+C to stop.

## Try it without applying anywhere

```powershell
.\scripts\demo.ps1 -Offline -Reset
```

Upload `backend/agent/applicant/example_resume.pdf`, finish setup, then paste
`https://job-boards.greenhouse.io/fakecompany/jobs/1001` (or the Ashby one,
`https://jobs.ashbyhq.com/fakecompany/00000000-0000-4000-8000-000000001001`) and press **Apply**.
The agent fills a local test form, so nothing goes online.

## Run it in the cloud

The API, the agent and its browser run together in one container on a server; the web app
(still on your machine for now) talks to it, and people sign in with Google through
[Clerk](https://clerk.com). Each person's data is kept in their own folder on the server's disk.

**1. Clerk (once).** Create an application at clerk.com with **Google** as the only sign-in
option. From its *API keys* page copy the publishable key (`pk_...`) and the secret key
(`sk_...`).

**2. The server.** With [Fly.io](https://fly.io) (`fly auth login` first), from `backend/`:

```powershell
fly launch --no-deploy --copy-config
fly volumes create autoapply_data --size 3
fly secrets set CLERK_PUBLISHABLE_KEY=pk_... CLERK_SECRET_KEY=sk_... ALLOWED_ORIGINS=http://localhost:5173
fly deploy
```

`https://<your-app>.fly.dev/api/health` should answer `{"ok": true, ... "authMode": "clerk"}`.
Any other machine with Docker works the same way: copy `backend/deploy/api.env.example` to
`backend/deploy/api.env`, fill it in, and run `docker compose up --build` from `backend/` (put
HTTPS in front of port 8080).

**3. The web app.** Create `frontend/.env.cloud.local`:

```
VITE_API_BASE_URL=https://<your-app>.fly.dev/api
VITE_CLERK_PUBLISHABLE_KEY=pk_...
```

Then, from `frontend/`, run `npm run dev:cloud` and open http://localhost:5173.

Server settings (`fly secrets set NAME=value`, or `deploy/api.env`):

| Setting                 | What it does                                                               |
| ----------------------- | -------------------------------------------------------------------------- |
| `AUTH_MODE`             | `clerk` in the container. `local` (the default elsewhere) is the one-user demo with no real sign-in. |
| `CLERK_PUBLISHABLE_KEY` | Which Clerk application's sign-ins are accepted.                           |
| `CLERK_SECRET_KEY`      | Lets the server read a new person's name and email, and delete their Clerk user when they delete their account. |
| `ALLOWED_ORIGINS`       | Comma-separated addresses the web app is served from. Only those pages may call the API. |
| `MAX_CONCURRENT_RUNS`   | How many browsers may fill or submit at once, across everyone. Default `2`. |
| `SUBMIT_REAL_FORM`, `ANTHROPIC_API_KEY`, `CONFIRM_TIMEOUT_S`, `FAKE_GREENHOUSE` | As in Notes below, for everyone on the server. |

Things to know:

- **One machine, stopped when idle.** Fly stops the machine a few minutes after the last request
  (nothing is charged for it while stopped; the data volume is) and starts it again on the next
  one, so the first page after a pause takes a little longer. The web app keeps checking job
  progress while it is open, so the machine only stops once nobody has it open. Stopping,
  restarting or redeploying closes the open browsers: a form waiting for review is filled again
  at Submit, and queued jobs wait until the machine is started. For always-on, set
  `auto_stop_machines = "off"` and `min_machines_running = 1` in `backend/fly.toml`. Never scale
  to several machines: a filled form is an open browser inside one server process.
- **Nobody sees the server's browser window**, so the live browser in the web app is the only way
  to reach a form (for a CAPTCHA, say). Sites may challenge a data-center address more often than
  your home one.
- **Data** is in the volume mounted at `/data`, one folder per person under `users/`. *Delete
  account* removes that folder and the person's Clerk user.

## Run the tests

From `backend/`:

```powershell
.venv\Scripts\python -m pytest agent/tests server/tests
.venv\Scripts\python server/e2e/run_browser_e2e.py
```

The second command clicks through the whole app in a hidden browser against the test form. Stop
the demo first, because it needs ports 8080 and 5173.

From `frontend/`:

```powershell
npm test
```

## Notes

- **Settings** are in `backend/agent/.env`. Restart after changing them.

  | Setting              | What it does                                                                  |
  | -------------------- | ----------------------------------------------------------------------------- |
  | `SUBMIT_REAL_FORM`   | `false` (default): Submit records the application but never sends it. `true`: Submit really applies. |
  | `ANTHROPIC_API_KEY`  | Optional. With a key, Claude drafts answers. Without one, the agent asks you. |
  | `AGENT_SHOW_BROWSER` | `true` shows the browser window while the agent fills the form.              |
  | `AGENT_SLOW_MO_MS`   | Slows the browser down so you can follow it, e.g. `250`.                      |
  | `CONFIRM_TIMEOUT_S`  | How long Submit waits for the thank-you page. Default `90`.                   |
  | `BROWSER_CDP_URL`    | Optional. Use a Chromium that is already running elsewhere (its DevTools address, e.g. `http://host:9222` or a `wss://` URL) instead of launching one here. |

- **The live browser.** While the agent fills a form, and afterwards while you review it, the
  form's browser is shown live to the left of its answers (open a job from **Applying now**, or
  **Review**). Click the picture to scroll, click and type in the form yourself; click outside
  it to stop. It works with `AGENT_SHOW_BROWSER` off, and it is how you reach the form when the
  browser runs on another machine.

- **Submit** presses the Submit button on the form the agent already filled. If the site emails
  you a verification code (Greenhouse does this), the app asks you for it: type it into the box
  in AutoApply, and the agent enters it into the form and submits it. No need to find the
  browser window, and it works with `AGENT_SHOW_BROWSER` off too. A filled form's window is
  never closed until the application is confirmed and screenshotted,
  you close it yourself, or the server stops.
- **Your data** (profile, resume, answers, jobs, screenshots) stays on your computer in
  `backend/data/` when you run it locally, which is never committed. `.\scripts\demo.ps1 -Reset` deletes it and starts
  fresh.
- **Supported sites:** Greenhouse and Ashby forms are filled automatically. Other links are
  handed to you to finish by hand. On Ashby, questions the agent can't fill yet (dates, rating
  scales) and the optional demographic survey are left for you to fill in the browser window.
- **Two terminals instead of `demo.ps1`** (also how to run it on macOS/Linux, using
  `.venv/bin/python`): run `.venv\Scripts\python -m server` from `backend/`, and
  `npm run dev:api` from `frontend/`.
- **The agent on its own, without the web app:** from `backend/`, run
  `.venv\Scripts\python -m agent <greenhouse or ashby job link> --show`. It reads its profile from
  `PROFILE_PATH` in `backend/agent/.env`, not from the web app.
