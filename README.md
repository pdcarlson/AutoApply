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
5. Paste a Greenhouse job link into the Inbox and press **Apply**. Answer any questions the agent
   asks, then review the filled form and press **Submit**.

Press Ctrl+C to stop.

## Try it without applying anywhere

```powershell
.\scripts\demo.ps1 -Offline -Reset
```

Upload `backend/agent/applicant/example_resume.pdf`, finish setup, then paste
`https://job-boards.greenhouse.io/fakecompany/jobs/1001` and press **Apply**. The agent fills a
local test form, so nothing goes online.

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

- **Submit** presses the Submit button on the form the agent already filled. If the site emails
  you a verification code, type it into that browser window (turn on `AGENT_SHOW_BROWSER`). A
  filled form's window is never closed until the application is confirmed and screenshotted,
  you close it yourself, or the server stops.
- **Your data** (profile, resume, answers, jobs, screenshots) stays on your computer in
  `backend/data/`, which is never committed. `.\scripts\demo.ps1 -Reset` deletes it and starts
  fresh.
- **Supported sites:** Greenhouse and Lever forms are filled automatically. Ashby links are
  accepted, but those jobs are handed to you to finish by hand. In offline mode,
  `https://jobs.lever.co/fakelever/0a1b2c3d-4e5f` opens a local test Lever form.
- **Lever: you press Submit in your own browser.** Lever turns applications from the agent's
  browser away ("There was an error verifying your application"), so for a Lever job **Review**
  offers **Open the form to submit**. Drag the **Fill with AutoApply** button shown there to your
  bookmarks bar once; on the form, click it and the form fills in (any browser, no extension).
  Check it, press Submit, then **I submitted it**. In Chrome, the optional extension in
  `extension/` fills the form by itself as it opens (see `extension/README.md`).
- **Protected steps:** the agent never types into a CAPTCHA, sign-in, password or Social Security
  number field. It fills the rest, leaves the form window open and moves the job to **Needs
  you**. Do that step in the window and press Submit there (turn on `AGENT_SHOW_BROWSER`); the
  application is recorded when the thank-you page appears.
- **Two terminals instead of `demo.ps1`** (also how to run it on macOS/Linux, using
  `.venv/bin/python`): run `.venv\Scripts\python -m server` from `backend/`, and
  `npm run dev:api` from `frontend/`.
- **The agent on its own, without the web app:** from `backend/`, run
  `.venv\Scripts\python -m agent <greenhouse job link> --show`. It reads its profile from
  `PROFILE_PATH` in `backend/agent/.env`, not from the web app.
