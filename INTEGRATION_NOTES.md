# Integration notes: Lever and US8 on the latest demo

Branch `dash/lever`, built on `demo` at `310582d` (the first/middle/last name split). It adds
four things and nothing else. Ordinary Greenhouse forms fill, review and submit exactly as before.

## 1. Lever forms are filled (US5, US6, F5, F6)

Lever works the same way as Greenhouse. When a link is added, the posting is read (company, role,
location and every question). The agent answers from the profile, setup answers and Answer bank,
asks about the rest in Needs you, fills the form and holds it for review. Ashby links are still
only recorded.

| File | Change |
| --- | --- |
| `backend/agent/forms/lever_form.py` (new) | `LeverForm`, a sibling of `GreenhouseForm` behind the same `AtsForm` base. Lever has no public questions API, so `parse_page` reads the apply page's HTML into the same `FormField`s. Fills text, textarea, dropdown, radio, checkbox, file and the city box (types the city, picks the matching "City, ST, USA" suggestion). Waits for Lever to finish reading the resume. Skips demographic questions and pronouns. |
| `backend/agent/forms/__init__.py` | `form_for` returns a `LeverForm` for Lever links. |
| `backend/agent/applicant/profile.py` | `full_name` (first, middle, last) for Lever's single name box. |
| `backend/server/routes/jobs.py` | Lever links accepted; `_form_details` (was `_greenhouse_details`) reads both sites. |
| `backend/server/agent_bridge.py` | Offline mode maps `jobs.lever.co/fakelever/0a1b2c3d-4e5f` to `agent/tests/fake_forms/lever_form.html`. |
| `backend/server/applications.py` | `LV-` confirmation references. |
| `frontend/src/api/types.ts`, `src/lib/jobLinks.ts`, `src/mocks/` | `Lever` as an `Ats`; the Inbox accepts Lever links. |

Checked live, dry run only: all 14 fields on a real Zoox Lever form filled correctly, and
nothing was sent. Lever forms carry an invisible hCaptcha. If it ever shows a challenge, US8 hands
it to the person.

**When Lever's bot check turns an application away.** After Submit, Lever's invisible hCaptcha
can reject the agent's browser ("There was an error verifying your application"), and retrying in
that window keeps failing. The agent now recognizes this (`LeverForm.is_blocked`), whether the
app pressed Submit or the person did in the held window (`FormSession` reports it through
`on_blocked`), and moves the job to Needs you: finish it in your own browser, copying the answers
from "See its answers", then press "I submitted it". The agent never tries to get past the check.
The Needs-you card now shows the job's real reason instead of always saying "CAPTCHA".

Two fixes found on real postings: pages with tracking pixels never go network-idle, so the
filler now waits a few seconds and carries on; and a cookie banner pinned over the page caught
mouse clicks, so choices and place suggestions are now set on the element itself.

## 2. Filling in the person's own browser (the `extension/` folder)

Lever rejects applications submitted from the agent's browser, and no amount of retrying in that
window helps. The agent must not disguise itself to get past that. So the last step moves to the
person's own browser: a small Chrome extension fills the same answers there, and the person
reviews the form, presses Submit and does any challenge themselves. This is how browser autofill
tools such as Simplify work.

| File | What it does |
| --- | --- |
| `extension/manifest.json` | Chrome extension (Manifest V3). Runs on `jobs.lever.co`; may only talk to `localhost:8080`. |
| `extension/content.js`, `panel.css` | A small panel on the application form with **Fill in my answers**. On the thank-you page it tells AutoApply the application went out. Never presses Submit. |
| `extension/fill.js` | Puts a plan's answers into a Lever form: text, dropdowns, radio buttons, checkboxes, the city box and the resume. Reports what it couldn't fill. |
| `extension/background.js` | Fetches from the local server for the page. |
| `backend/server/browser_fill.py`, `routes/extension.py` | `GET /extension/plan?url=` (the job's answers by page link; Claude is never called; protected fields are named but never given a value), `GET /extension/jobs/:id/resume`, `POST /extension/jobs/:id/submitted`. |

Checked: `fill.js` against the fake Lever page in the test suite; by hand, the loaded extension
end to end in Chromium against a local test server (fill, resume, recorded on the thank-you
page); and `fill.js` on two live Lever forms as a dry run (36 of 36 and 13 of 13 fields, nothing
sent). Not yet checked: a real submit from a person's own Chrome. Greenhouse is not covered by
the extension yet; it needs its own fill function next to `fillLever`.

## 3. Protected field handoff (US8, F8, SE2)

Ported from `backend/features/protected_handoff/` on the `dash` branch into the agent `demo` runs.
The agent never types into a CAPTCHA, sign-in, password or SSN field, and never asks for one in
the app, so the value can't be saved.

1. `ApplyRun.run` skips any question the site lists that is protected: not answered, not asked.
2. `ApplyRun.drive` scans the open page after it loads and again after filling, for visible
   protected fields and CAPTCHA frames.
3. If any are found, the rest is filled, Submit is never pressed, and the run ends with the new
   status `handoff`. The window is held open like a `ready` one.
4. The server moves the job to the existing `handoff` state with a plain reason and watches the
   window. When the person finishes the step and presses Submit there, the thank-you page is
   detected, the screenshot saved and the application recorded. "I submitted it" also works.
5. A CAPTCHA that only appears after Submit gets its own Needs-you wording.

| File | Change |
| --- | --- |
| `backend/agent/forms/protected.py` (new) | `ProtectedFieldDetector`, one check class per kind. Reads labels and attributes only, never values. Invisible CAPTCHAs (the badge on every Greenhouse and Lever form) don't count. |
| `backend/agent/runner/apply_run.py` | `RunResult.protected`, the `handoff` status, the page scans, the after-Submit CAPTCHA check. |
| `backend/server/worker.py` | `_to_protected`: job to `handoff`, filled fields kept, window watched. |
| `backend/server/applications.py` | Needs-you wording; a submit that has to refill and finds a protected step answers `409 protected_step`. |

To add a new kind of protected step, write one `ProtectedCheck` subclass and add it to the list
in `ProtectedFieldDetector.__init__`. This does not get the agent past bot detection, on purpose:
when a site challenges the agent, the challenge goes to the person.

## 4. Fix: resume upload response

`POST /api/resume` could answer with sections already in it, because the parse thread shared the
list being sent. It now always answers with an empty list (`server/routes/setup.py`). This was
the one test that failed on a fast machine.

## Tests

- New: `server/tests/test_browser_fill.py`, `server/tests/test_extension_fill.py`,
  `agent/tests/test_lever.py`, `server/tests/test_lever_jobs.py`,
  `agent/tests/test_protected.py`, `server/tests/test_protected_handoff.py`, plus Lever cases in
  `test_jobs_routes.py`, `jobLinks.test.ts` and `InboxPage.test.tsx`.
- Fake forms: `fake_forms/lever_form.html`, `fake_forms/fake_captcha.html`, and
  `?protect=ssn|password|captcha` on the fake Greenhouse form.
- Run: `pytest agent/tests server/tests` (backend), `npm test` (frontend),
  `python server/e2e/run_browser_e2e.py` (browser end-to-end).
