# Auto Apply — frontend

React + TypeScript single-page app for Auto Apply. Every screen is built; all data comes from the
backend API described in [docs/api.md](docs/api.md). Until the backend exists, development runs
against a mock API in the browser.

## Getting started

Requires Node 20+.

    npm install
    npm run dev          # http://localhost:5173, served by the in-browser mock API

To work against a real backend running on `localhost:8080` instead:

    npm run dev:api      # proxies /api to VITE_API_PROXY_TARGET (see .env.backend)

| Script              | What it does                                        |
| ------------------- | --------------------------------------------------- |
| `npm run dev`       | Dev server with the mock API                        |
| `npm run dev:api`   | Dev server talking to a real backend                |
| `npm run dev:cloud` | Dev server talking to a backend in the cloud        |
| `npm run build`     | Typecheck, then production build into `dist/`       |
| `npm run preview`   | Serve the production build                          |
| `npm test`          | Run the tests once (Vitest + Testing Library + MSW) |
| `npm run lint`      | ESLint                                              |
| `npm run format`    | Prettier                                            |
| `npm run typecheck` | TypeScript only                                     |

## Configuration

Set in `.env.development`, `.env.backend`, `.env.production`, or a git-ignored `.env.*.local`.

| Variable                     | Meaning                                                                |
| ---------------------------- | ---------------------------------------------------------------------- |
| `VITE_API_BASE_URL`          | Where API requests go. Default `/api`; may be a full origin.           |
| `VITE_API_MOCKING`           | `enabled` serves `/api` from `src/mocks` (development only).           |
| `VITE_API_PROXY_TARGET`      | Dev server only: forward `/api` to this backend.                       |
| `VITE_CLERK_PUBLISHABLE_KEY` | Set: sign in with Google through Clerk. Unset: the local demo sign-in. |

Sign-in comes in two kinds, chosen at build time by `VITE_CLERK_PUBLISHABLE_KEY`:

- **Unset** (the mock API and the local backend): "Begin Onboarding" asks the backend, which
  signs the one local user in.
- **Set** (a backend running with `AUTH_MODE=clerk`): Clerk signs the person in with Google and
  every API request carries its session token as `Authorization: Bearer <token>`
  (`src/api/authToken.ts`). The live browser socket sends it as a WebSocket subprotocol and
  screenshots are fetched with it (`src/api/useApiImage.ts`), since neither can set headers.
  `src/auth/` holds everything Clerk-specific, and it is only downloaded by builds that use it.

`npm run dev:cloud` runs this app against a backend in the cloud; put `VITE_API_BASE_URL` and
`VITE_CLERK_PUBLISHABLE_KEY` in `.env.cloud.local`. The backend must list this app's address in
`ALLOWED_ORIGINS`.

## Mock API (development only)

`src/mocks` implements every endpoint in `docs/api.md` with [MSW](https://mswjs.io), backed by an
in-memory database with placeholder fixtures (fictional companies, a test user). It includes a
small stand-in agent that fills queued jobs one field per second, so polling, progress, questions,
CAPTCHA hand-offs, and "ready for review" can all be exercised.

- State is kept in `localStorage`, so reloading keeps you signed in.
- Run `autoApplyMocks.reset()` in the browser console to start over, signed out.
- "Begin Onboarding" signs you straight in; the real backend redirects to Google.
- The mocks are loaded with a dynamic import behind `import.meta.env.DEV`, so they are never part
  of a production build. Delete `src/mocks` and `public/mockServiceWorker.js` once the backend is
  live (tests use the same handlers, so move or replace them at the same time).

## Project layout

    src/
      api/          API contract (types.ts), fetch client, one function per endpoint, React Query hooks
      app/          App root, providers (theme, toasts, overlays), routes and route guards
      components/ui Shared UI: buttons, form controls, chips, modal/drawer, field list, timeline…
      features/     One folder per area: auth, setup, inbox, applications, answers, profile, settings
      layouts/      Signed-in shell (sidebar, bottom nav), setup frame, page wrapper
      lib/          Pure helpers: formatting, job status rules, link and file validation
      mocks/        Dev/test mock API (see above)
      styles/       Design tokens (light/dark) and global base styles
      test/         Test setup and render helpers

Conventions:

- **Server state** lives in TanStack Query (`src/api/queries/`). Components never call `fetch`
  directly. Jobs and agent status poll every 2 s while the agent is working.
- **UI state** that several screens share (open drawer/modal, toasts, theme) lives in small React
  contexts under `src/app/providers`.
- **Styling** is CSS Modules next to each component, built on the tokens in
  `src/styles/tokens.css`. Global CSS is limited to the reset, form-control drawing, and a few
  text utilities (`.small`, `.muted`, `.eyebrow`, `.h1`…).
- **Routes**: `/sign-in`, `/auth/callback`, `/setup/{resume,profile,questions}`, `/inbox`
  (`?job=<id>` opens one), `/applications` (`?filter=ready` etc.), `/answers`,
  `/profile` (`#education` etc. scrolls to a section), `/settings`, `/account-deleted`.

## Where the backend takes over

The frontend only displays and edits; it doesn't decide anything the agent decides. Specifically,
the backend is responsible for:

- Google OAuth and the session cookie (`POST /auth/google` returns the authorization URL; the
  backend's callback redirects to `/auth/callback`, with `?error=access_denied` on cancel).
- Resume parsing, profile checks against postings (`checks`, `reason`, `skipSuggested`), and the
  fill estimate (`formSummary`).
- Running the agent: queue order, daily limit, confidence scoring, when to ask, CAPTCHA hand-off,
  screenshots, and confirmation references.
- Interpreting the user's plain-words replies to questions (`question.messages`,
  `proposedAnswer`, `pickOptions`) and saving answers to the Answer bank.
- Validating pasted links (closed postings, duplicates). The frontend's check in
  `src/lib/jobLinks.ts` is only for instant feedback on obviously wrong links; only Greenhouse
  and Ashby are supported.

## Not done yet

- Background updates use polling. If the backend adds server-sent events or a WebSocket, replace
  the `refetchInterval`s in `src/api/queries/` with cache updates from the stream.
- The "Terms and Privacy policy" text on the sign-in page has no links yet.
- The old patched-bundle prototype is in `../prototype/` for visual reference only.
