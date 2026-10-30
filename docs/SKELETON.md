# Skeleton: what's built and what's next

| Area | Files | Stories | Status |
| --- | --- | --- | --- |
| Sign in | `pages/SignIn.jsx`, `app/deps.py` | US1 | UI only; every request uses a demo user |
| Resume + profile | `pages/Onboarding.jsx`, `routers/profile.py` | US2, US3 | Upload saves the file and profile edits save; parsing not built |
| Apply from link | `pages/Inbox.jsx`, `routers/applications.py`, `services/ats.py` | US5, US16 | Works: checks the site, blocks duplicates, enforces the daily limit, queues the job |
| Agent | `worker/run.py`, `worker/agent.py` | US6 | Spike: opens a fresh browser, loads the posting, screenshots it, then parks it in Needs you |
| Needs you | `pages/NeedsYou.jsx` | US7, US8, US13 | UI and skip work; sending answers back is not built |
| Answer bank | `pages/AnswerBank.jsx`, `routers/answers.py` | US9, US10 | Add, edit and delete work; the agent doesn't reuse answers yet |
| Tracker | `pages/Applications.jsx` | US11, US12 | List, filters and CSV export work; screenshot links are placeholders |
| Delete account | `routers/users.py` | US17 | Deletes the database rows; files on disk aren't deleted yet |

Search the code for `TODO(US` to see every open piece.
