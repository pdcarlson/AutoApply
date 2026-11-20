# AutoApply frontend

React + TypeScript single-page app. Setup, environment variables and the API it calls are in the
[root README](../README.md).

## Scripts

| Script              | What it does                                      |
| ------------------- | ------------------------------------------------- |
| `npm run dev`       | Dev server at http://localhost:5173               |
| `npm run build`     | Typecheck, then production build into `dist/`     |
| `npm run preview`   | Serve the production build                        |
| `npm test`          | Run the tests once (Vitest, Testing Library, MSW) |
| `npm run lint`      | ESLint                                            |
| `npm run format`    | Prettier                                          |
| `npm run typecheck` | TypeScript only                                   |

`npm run dev` and `npm run build` read `VITE_API_BASE_URL` and `VITE_CLERK_PUBLISHABLE_KEY` from
`.env.local` (copy `.env.example`). Without the Clerk key the app shows an error instead of
starting. Tests need no env file.

## Sign-in

Clerk signs the person in with Google, and every API request carries Clerk's session token as
`Authorization: Bearer <token>` (`src/api/authToken.ts`). The live browser socket sends it as a
WebSocket subprotocol and screenshots are fetched with it (`src/api/useApiImage.ts`), since
neither can set headers. `src/auth/` holds everything Clerk-specific.

## Layout

    src/
      api/          API contract (types.ts), fetch client, one function per endpoint, React Query hooks
      app/          App root, providers, routes and route guards
      auth/         Clerk sign-in
      components/   Shared UI
      features/     One folder per area: auth, setup, inbox, jobs, applications, answers, profile, settings
      layouts/      Signed-in shell, setup frame, page wrapper
      lib/          Pure helpers: formatting, job status rules, link and file validation
      mocks/        MSW fake backend for tests
      styles/       Design tokens (light/dark) and global base styles
      test/         Test setup and render helpers

Coding conventions are in [CODING_STANDARDS.md](../CODING_STANDARDS.md).
