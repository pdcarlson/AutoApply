# AutoApply

How to run the agent that fills out Greenhouse job applications.

1. Install Python 3.12 or newer.
2. Open a terminal in the `backend` folder.
3. Run `pip install -r agent/requirements.txt`
4. Run `python -m playwright install chromium`
5. Copy `agent/.env.example` to `agent/.env`
6. If you have an Anthropic API key, paste it after `ANTHROPIC_API_KEY=` in `agent/.env`. Without one, the agent asks you more questions.
7. Run `python -m agent https://job-boards.greenhouse.io/cloudflare/jobs/8245211 --show` with any Greenhouse job link.
8. Answer the questions it asks in the terminal. Your answers are saved, so it won't ask again.
9. Look at the screenshot it saves in `agent/runs`. It fills the form but doesn't press Submit while `SUBMIT_REAL_FORM=false` is in `agent/.env`.
10. To use your own info instead of the fake example, copy `agent/applicant/example_profile.json` and your resume into a new `agent/private` folder, edit the copy, and set `PROFILE_PATH=private/my_profile.json` in `agent/.env`. That folder is never committed.
11. Run `python -m pytest agent/tests` to run the tests.

## Run the demo

The demo is the web app in `frontend/` talking to a local API in `backend/server/`. The API drives
the same agent as above, keeps everything in JSON files, and has a single local user.

Once, from `backend/`, set up the Python environment (Python 3.12, or 3.11):

```powershell
uv venv .venv                                   # or: python -m venv .venv
uv pip install --python .venv -r server/requirements.txt
                                                # or: .venv\Scripts\python -m pip install -r server/requirements.txt
.venv\Scripts\python -m playwright install chromium
```

and from `frontend/`, run `npm install` (Node 22).

Then use two terminals.

1. Terminal 1, from `backend/`: `.venv\Scripts\python -m server`. The API listens on
   http://127.0.0.1:8080. Ctrl+C stops it.
2. Terminal 2, from `frontend/`: `npm run dev:api`, then open http://localhost:5173. This runs
   the real frontend against the API (`npm run dev` instead uses the built-in mock API).

`scripts\demo.ps1` starts both in one terminal: `.\scripts\demo.ps1 -Offline -Reset` (see the
switches with `Get-Help .\scripts\demo.ps1 -Detailed`).

### Offline demo with the fake Greenhouse form

Set these in terminal 1 before `python -m server`:

```powershell
$env:FAKE_GREENHOUSE = "true"   # the fakecompany link below opens a local form, not Greenhouse
$env:USE_CLAUDE = "false"       # don't call Claude even if agent/.env has a key
```

Sign in, upload `backend/agent/applicant/example_resume.pdf`, check the profile, answer the
common questions and confirm. Then paste
`https://job-boards.greenhouse.io/fakecompany/jobs/1001` (or `/1002`) and press Apply. The agent
fills `backend/agent/tests/fake_forms/greenhouse_form.html` in a headless browser, so nothing goes
online. It asks you about the two questions it can't answer (sponsorship, and why you want to work
there) in the Inbox, then holds the filled form under Applications for your review.

Other links only work with `FAKE_GREENHOUSE` off: the agent then reads the real posting from
Greenhouse and fills the real form. Without Claude (no key, or `USE_CLAUDE=false`) the agent asks
you about every field it can't fill from your profile and Answer bank.

Two more settings help when you show it to someone: `AGENT_SHOW_BROWSER=true` opens the browser
window so you can watch it fill, and `AGENT_SLOW_MO_MS=250` slows it down enough to follow.

### What Submit does: `SUBMIT_REAL_FORM`

`SUBMIT_REAL_FORM` (in `backend/agent/.env`, `false` there) is the only switch that decides
whether the agent presses the form's Submit button. A variable set in the terminal wins over the
file.

- `false`: Submit in the review dialog doesn't touch the form. The job still moves to
  Applications (with the screenshot taken when it was filled), with no confirmation and a "Not
  sent: SUBMIT_REAL_FORM is off" line in its timeline, so you can walk through the whole flow
  without sending anything.
- `true`: Submit fills the form again, presses its Submit button and checks for the confirmation
  page. With
  `FAKE_GREENHOUSE=true` and the fakecompany link that's the local fake form, which shows a
  confirmation reference. **With any other link it really applies to that job.**

### Where the data lives, and how to reset it

Everything (profile, resume, answers, jobs, applications, screenshots) is in `backend/data/`,
which has its own `.gitignore`, so none of it is committed. Set `AUTOAPPLY_DATA_DIR` to use
another folder. Run one server per data folder.

The Answer bank starts empty and only holds answers you give: your setup answers, replies to the
agent's questions, and answers you add yourself. `SEED_BANK_FROM_PROFILE=true` is a developer
option that copies the `answers` from `PROFILE_PATH` into a new bank once. Leave it off for real
use: the example profile's answers are test data, not yours.

To start over, stop the server and delete `backend/data/` (or run `.\scripts\demo.ps1 -Reset`).
**Settings → Delete account** in the app does the same while the server runs.

### End-to-end checks

From `backend/`, both run only against the fake form, on a fresh temporary data folder:

- `.venv\Scripts\python -m pytest server/tests -m e2e` drives the whole flow through the API with
  the real agent worker, with `SUBMIT_REAL_FORM` off and on.
- `.venv\Scripts\python server/e2e/run_browser_e2e.py` starts the API and `npm run dev:api` itself
  (ports 8080 and 5173 must be free) and clicks through the real frontend in headless Chromium,
  from sign-in to the submitted application's screenshot. It saves a PNG of each step in
  `<temp data folder>\e2e-shots` and prints where. Add `--dry-run` for `SUBMIT_REAL_FORM=false`,
  `--headed` to watch.
