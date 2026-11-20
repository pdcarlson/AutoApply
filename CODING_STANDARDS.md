# Coding Standards

How code in AutoApply should look. The backend model is the original agent in
`backend/agent/` (as written on the `pdcarlson/agent` branch): simple, object-oriented, and easy
for a person to read. When this guide and that code disagree, this guide wins.

The goal: Set coding standards that the entire repo can follow.

The guide has two parts: [Backend (Python)](#backend-python) and
[Frontend (TypeScript and React)](#frontend-typescript-and-react). Some rules apply to both:
spell names out, comments explain *why*, keep files around 200 lines, and leave ticket numbers
out of the code.

---

# Backend (Python)

## 1. Files and folders

- **One idea per file.** A file holds one main class (or one small group of closely related
  classes), plus any small helpers only that class uses.
- **Folders group one area of the domain:** `forms/`, `answers/`, `jobs/`, `applicant/`,
  `runner/`.
- **File names are `snake_case` and name the thing inside:** `job_link.py` holds `JobLink`,
  `application_log.py` holds `ApplicationLog`.
- **Size limits (soft):** about 200 lines per file and 30 lines per function. Going over means
  the file or function is doing more than one thing and should be split.

## 2. Naming

| Kind | Style | Example |
|---|---|---|
| Class | `PascalCase` noun from the domain | `JobLink`, `ApplicationLog`, `Answerer` |
| Function, method, variable | `snake_case` | `read_fields`, `form_field` |
| Constant | `UPPER_CASE`, at the top of the file | `CONFIDENCE_THRESHOLD`, `EMBED_URL` |
| Enum member | `UPPER_CASE` | `RunStatus.SUBMITTED` |
| Internal helper | leading `_` | `_set_status`, `_fill_and_send` |
| Exception | `PascalCase` describing the problem, no `Error` suffix | `UnsupportedLink`, `DuplicateLink` |

- **Spell names out.** Use `form_field`, `screenshot_path`, `answer`, not `ff`, `shot`, `ans`.
  The only allowed abbreviations are `url`, `id` and `db`.
- **Functions start with a verb:** `parse`, `load`, `save_answer`, `read_fields`.
- **Booleans read as yes/no questions:** `is_confirmed`, `needs_sponsorship`, `required`.
- **A method is private (`_name`) when nothing outside its class calls it.** Tests may still
  call private helpers when that's the clearest way to test them.

## 3. Object-oriented design

- **Every concept in the domain is a class.** Jobs, forms, fields, answers, profiles,
  applications and runs are objects, not loose dicts or bundles of functions.
- **Use `@dataclass` for objects that mostly hold data** (`FormField`, `FieldAnswer`,
  `RunResult`). **Use a plain class for objects that do work** (`Answerer`, `ApplyRun`).
- **Use an abstract base class when each site behaves differently.** `AtsForm` defines the
  interface, and `GreenhouseForm` and `AshbyForm` implement it. Code that uses a form never
  checks which site it is on.
- **Other ways of creating an object are `@classmethod`s:**

  ```python
  link = JobLink.parse(url)
  profile = Profile.load(PROFILE_PATH)
  ```

- **Pass dependencies in through the constructor.** A class doesn't create the services it
  needs, so tests can hand in fakes:

  ```python
  class Answerer:
      def __init__(self, profile: Profile, ask_claude: Callable, threshold: int = CONFIDENCE_THRESHOLD):
  ```

- **Small stateless helpers may be module-level functions** (`fits`, `normalize`,
  `greenhouse_ids`), kept in the same file as the class that uses them. If a helper needs
  state, or more than one class uses it, it belongs on a class.

## 4. Data shapes

- **Code inside the backend works with dataclasses using `snake_case` fields**, not raw dicts.
- **Dicts only appear at the edges:** JSON on disk and the HTTP API. Converting happens in one
  place per class:

  ```python
  @dataclass
  class Application:
      job_id: str
      status: RunStatus

      @classmethod
      def from_json(cls, data: dict) -> "Application":
          """Build an Application from its stored JSON."""
          return cls(job_id=data["jobId"], status=RunStatus(data["status"]))

      def to_json(self) -> dict:
          """Return the camelCase JSON the frontend reads."""
          return {"jobId": self.job_id, "status": self.status.value}
  ```

- **camelCase keys exist only inside `to_json`/`from_json`.** Nowhere else in Python.

## 5. Enums for fixed sets of values

Any value that can only be one of a known list is a `str`-based `Enum`, so the JSON stays the
same and typos fail loudly:

```python
class RunStatus(str, Enum):
    """How a run ended."""

    NEEDS_INPUT = "needs_input"
    READY = "ready"
    SUBMITTED = "submitted"
    FAILED = "failed"
```

Statuses, field kinds (`text`, `select`, `file`…), sites (`greenhouse`, `ashby`…) and answer
sources (`profile`, `saved`, `claude`) are all Enums. Don't write `if status == "failed"`. Write
`if status is RunStatus.FAILED`.

## 6. Type hints

- **Hint the parameters and return values of public functions and methods.**
- **Dataclass fields are always hinted** (Python requires it).
- **Don't hint local variables or private helpers** unless it really helps the reader.

```python
def answer(self, form_field: FormField) -> FieldAnswer | None:
    """Return a FieldAnswer, or None if the agent should ask the applicant instead."""
```

## 7. Docstrings and comments

- **Every file starts with a one-line docstring** saying what the file is for, in plain English:

  ```python
  """Reads a job link and works out which site it's on."""
  ```

- **Every class and every function or method has a one-line docstring.** Functions start with a
  verb and say what comes back, including the empty case:

  ```python
  def saved_answer(self, question: str) -> str | None:
      """Return the saved answer to this question, or None."""
  ```

- **A second paragraph is allowed only when one line truly can't cover it.** No `Args:` or
  `Returns:` sections. The type hints and the one line do that job.
- **Comments explain *why*, never *what*.** If the code needs a comment to say what it does,
  rename things until it doesn't.

  ```python
  # Good: explains a surprise
  # The resume upload breaks if a file goes in before the page's scripts finish loading
  page.wait_for_load_state("networkidle")

  # Bad: repeats the code
  # wait for the network to be idle
  page.wait_for_load_state("networkidle")
  ```

- **Write comments in plain English.** Leave out ticket numbers ("WP2"), people's names and
  "TODO" notes that will never be done. A "TODO" is allowed only with the reason it isn't done
  yet.

## 8. Errors

- **Inside the domain, raise a custom exception** for anything the caller should handle.
  Exceptions inherit from a built-in (usually `ValueError`) and carry a friendly full-sentence
  message a user could read:

  ```python
  class UnsupportedLink(ValueError):
      """The link isn't a job on a site AutoApply supports."""

  raise UnsupportedLink("That Greenhouse link doesn't point at a single job.")
  ```

- **At the edge, turn exceptions into result objects.** `ApplyRun.run` catches page errors and
  returns `RunResult(RunStatus.FAILED, reason)`, and API routes turn errors into HTTP
  responses. Exceptions don't escape to the user as stack traces.
- **Catch specific exceptions** (`PlaywrightError`, `anthropic.APIError`, `OSError`), never a
  bare `except:` or `except Exception` without a comment explaining why.

## 9. Output and logging

- **`print` only in command-line entry points** (`agent/__main__.py`).
- **Everywhere else, use `logging`**, with one logger per module:
  `log = logging.getLogger(__name__)`.

## 10. Configuration

- **All settings live in `settings.py`** (the agent) or `config.py` (the server). They're read
  from the environment once, and no other file calls `os.getenv`.
- **Magic numbers and URLs become named constants** at the top of the file that uses them, with
  a comment when the value isn't obvious.

## 11. Imports and formatting

- **Use absolute imports** (`from agent.forms.form_field import FormField`), grouped and
  separated by a blank line: standard library, third-party, then our own code.
- **Use `pathlib.Path`** for file paths, **f-strings** for formatting, and
  **`encoding="utf-8"`** on every file read and write.
- **Lines are at most 100 characters.** Run **pylint** before committing. A
  `# pylint: disable=...` comment needs a good reason, for example a `Profile` dataclass that
  really does have many fields.

## 12. Tests

- **Tests are plain pytest functions** in a `tests/` folder next to the code, one test file per
  module (`test_job_link.py` tests `job_link.py`).
- **Every test has a docstring stating the behaviour it checks:**

  ```python
  def test_fields_from_api():
      """The resume is one file field, and dropdown options come through."""
  ```

- **Use fakes, not mocks.** Pass fake objects or functions in through constructors
  (`fake_claude`), and keep saved fixtures (such as `tests/fake_forms/`) instead of calling real
  sites or APIs.

## Backend checklist before committing

- [ ] Each file has a one-line docstring and holds one idea, in roughly 200 lines or fewer.
- [ ] Every class, function and method has a one-line docstring.
- [ ] Domain data is in dataclasses, and camelCase appears only in `to_json`/`from_json`.
- [ ] Fixed sets of values are Enums.
- [ ] Public functions have type hints.
- [ ] Names are spelled out, and internal helpers start with `_`.
- [ ] Comments say *why*, with no ticket numbers.
- [ ] `print` appears only in command-line entry points.
- [ ] pylint passes at 100 characters per line, and tests pass.

---

# Frontend (TypeScript and React)

The frontend is a React app built with Vite, TanStack Query for server data, React Router and
CSS Modules. The aim is the same as the backend: clean, plain and easy to follow. Use the tools
we already have, and add a library or a layer of abstraction only when the code is clearly
worse without it.

**About object-oriented design:** React is built around function components and hooks, and
class components are a legacy style. So the frontend doesn't use classes. It gets the same
benefits (one clear responsibility, a small public surface, and dependencies passed in) from
components, hooks and typed modules instead.

## 13. Folders

| Folder | Holds |
|---|---|
| `src/app/` | Startup: router, route paths, guards, providers, query client |
| `src/api/` | Everything that talks to the backend: client, endpoints, query hooks, API types |
| `src/auth/` | Sign-in setup and actions |
| `src/components/ui/` | Reusable building blocks with no app logic (`Button`, `Spinner`, `Form`) |
| `src/layouts/` | The page frames around screens (`AppShell`, `Page`) |
| `src/features/<area>/` | One folder per screen or area (`inbox`, `profile`, `settings`) |
| `src/lib/` | Plain TypeScript helpers with no React (`format`, `jobLinks`, `jobStatus`) |
| `src/mocks/` | The MSW fake backend used in tests |
| `src/styles/` | Global CSS and design tokens |
| `src/test/` | Test setup and shared test helpers |

- **Code starts in the feature that uses it.** Move it to `components/ui/` or `lib/` only once a
  second feature needs it.
- **Features don't import from each other.** If two features need the same thing, move it to a
  shared folder.

## 14. Files and naming

| Kind | Style | Example |
|---|---|---|
| Component file | `PascalCase.tsx`, named after the component it exports | `JobRow.tsx` |
| Hook file | `useCamelCase.ts` | `usePauseToggle.ts` |
| Other module | `camelCase.ts` | `jobStatus.ts`, `queryClient.ts` |
| Styles | `<Component>.module.css`, next to the component | `JobRow.module.css` |
| Test | `<file>.test.ts(x)`, next to the file it tests | `InboxPage.test.tsx` |
| Component, type, interface | `PascalCase` | `JobRow`, `JobRowProps`, `Application` |
| Function, variable, prop | `camelCase` | `formatDay`, `isInProgress` |
| Constant | `UPPER_CASE`, with the unit in the name | `LIVE_POLL_MS`, `BASE_URL` |
| Event prop / handler | `onThing` for props, `handleThing` inside the component | `onApply`, `handleApply` |

- **One exported component per file.** Small private components only that file uses can stay
  in it. A file like `editors.tsx` that exports several large components should be split.
- **Spell names out,** the same as the backend. Allowed abbreviations: `url`, `id`, `db`, `api`.
- **Booleans read as yes/no:** `isLoading`, `hasResume`, or a plain adjective for props
  (`expanded`, `disabled`).

## 15. Components

- **Function components only,** declared as `export function Name(props)`, not as arrow
  functions assigned to variables.
- **Use named exports, never `export default`,** so a component has the same name everywhere it
  is imported. The only exception is when a tool requires a default export.
- **Props are an `interface` named `<Component>Props`**, declared right above the component and
  destructured in the signature, with defaults written there:

  ```tsx
  interface JobRowProps {
    job: Job;
    expanded: boolean;
    onApply: () => void;
  }

  export function JobRow({ job, expanded, onApply }: JobRowProps) {
  ```

- **Keep components small.** Around 150 lines for a component and 200 for a file. When a
  component grows, pull out a child component or a `useThing` hook.
- **Keep logic out of the JSX.** Work out values above the `return` (`const chip =
  jobChip(job)`). Plain logic with no React belongs in `src/lib/`, where it's easy to test.
- **Use semantic HTML first:** `<button type="button">` for actions, `<a>` / `<Link>` for
  navigation, `<label>` on every input, and `alt` on every image. Don't put `onClick` on a
  `div`.

## 16. Types

- **TypeScript is `strict`, with no `any`.** Use `unknown` and narrow it when a value really
  could be anything.
- **Use `interface` for object shapes and props, and `type` for unions and aliases:**

  ```ts
  export interface Application { id: string; status: ApplicationStatus; }
  export type ApplicationStatus = 'ready' | 'submitted' | 'failed';
  ```

- **Fixed sets of values are string-literal unions, not TypeScript `enum`s.** They match the
  backend's Enum values exactly, need no runtime code, and show up as plain strings in the JSON.
- **The API types in `src/api/types.ts` mirror the backend's JSON exactly** (camelCase).
  Components use these types directly, with no second "frontend model" layer on top.
- **Use `import type` for type-only imports** (ESLint enforces this).
- **Hint exported function parameters, and let TypeScript infer the rest** (locals and most
  return types).
- **Avoid `as` casts.** If you need one, the type is probably wrong. Tests may use `as` to build
  partial fixtures.

## 17. Server data (TanStack Query)

- **Components never call `fetch` or the endpoint functions directly.** All server data goes
  through hooks in `src/api/` (`useJobs()`, `useSaveProfile()`), so loading and caching work the
  same way everywhere.
- **The layers, from bottom to top:**
  1. `client.ts`: the one place that sends HTTP requests, adds auth and turns failures into
     `ApiError`.
  2. `endpoints.ts`: one plain function per backend endpoint.
  3. `queries.ts` (or one file per area under `src/api/` once it passes about 200 lines):
     `useQuery` / `useMutation` hooks.
- **Query keys live in the one `queryKeys` object.** Never write a key array inline.
- **Mutations invalidate or update the queries they change,** inside the hook, so components
  don't need to know about the cache.

## 18. State

Pick the simplest option that works, in this order:

1. **A derived value.** Calculate it while rendering. Don't copy it into state.
2. **Local `useState`** in the component that owns it.
3. **Lift the state up** to the nearest shared parent, and pass it down as props.
4. **The URL** (route params or search params), for anything that should survive a reload or a
   shared link: the open drawer, the selected tab, filters.
5. **React context** (in `src/app/providers/`), only for truly app-wide state such as overlays
   or toasts.

Server data is never copied into state. It stays in TanStack Query. Don't add a global state
library.

- **`useEffect` is for syncing with something outside React** (timers, sockets, the DOM). It
  isn't for calculating values or responding to a click. Put that logic in the event handler.

## 19. Styling

- **Use CSS Modules,** one per component (`import styles from './JobRow.module.css'`). Class
  names inside are `camelCase` (`styles.row`, `styles.open`).
- **Colors, spacing, fonts and radii come from the design tokens** (CSS variables in
  `src/styles/`). Don't hard-code hex values or pixel sizes that already exist as a token.
- **Use `cx(...)` to combine conditional classes:**
  `cx(styles.row, expanded && styles.open)`.
- **No inline `style={{}}`,** except for values calculated at runtime (such as a progress bar's
  width).

## 20. Comments

- **Exported components, hooks and functions get a one-line `/** ... */`** saying what they do,
  the same as backend docstrings. Add one to props and type fields whose meaning isn't obvious
  from the name.

  ```ts
  /** Joins class names, skipping falsy values. */
  export const cx = (...names: (string | false | null | undefined)[]) => ...
  ```

- **A file-header comment only where the file needs explaining,** such as `types.ts` describing
  the API contract.
- **Inline `//` comments explain *why*,** never *what*. No ticket numbers, and no
  commented-out code.
- **Section dividers (`// ===== Jobs =====`) are fine** in long type and query files. In any
  other file, needing one is a sign the file should be split.

## 21. Errors and loading

- **Every screen that loads data handles all three states:** loading (a `Spinner`), error (an
  `ErrorBox` showing the `ApiError`'s `message`) and success.
- **Show the backend's `message` to the user.** Branch on `code`, never on the message text.
- **Don't swallow errors.** An empty `catch {}` needs a comment explaining why ignoring the
  error is safe.

## 22. Configuration

- **Read `import.meta.env` only in a config spot:** `src/api/client.ts` (API URL)
  and `src/auth/config.ts` (Clerk). Everything else imports from
  those.
- **Magic numbers become named constants** at the top of the file, with the unit in the name
  (`LIVE_POLL_MS = 2000`).

## 23. Imports and formatting

- **Use `@/` for imports across folders, and `./` within the same folder.** Never `../../`.
- **Import order:** packages first, then `@/` imports, then `./` imports, then the CSS module last.
- **Prettier formats everything** (single quotes, 100-character lines, trailing commas).
  Don't hand-format, and don't argue with it.
- **Before committing, run `npm run lint`, `npm run typecheck` and `npm run format:check`.**
  All three must pass. An `eslint-disable` comment needs a reason on the same line.
- **No `console.log` in committed code.** `console.error` is allowed for errors that would
  otherwise be lost.

## 24. Tests

- **Tests use Vitest and Testing Library,** with MSW (`src/mocks/`) standing in for the backend.
  No mocking of `fetch` or our own modules.
- **Test what the user sees and does:** find elements by role, label or text (`getByRole`,
  `findByLabelText`), and interact with `userEvent`. Don't test internal state or CSS classes.
- **`describe` names the component, and each `it` reads as a sentence about behaviour:**

  ```tsx
  describe('QuestionPanel', () => {
    it('shows a reply box for a free-text field', async () => {
  ```

- **Pure helpers in `src/lib/` get plain unit tests.** They're the cheapest tests to write, so
  logic belongs there.
- **Mock data (`src/mocks/db.ts`) may run past the size limit,** but split it by area once it
  gets hard to find things in.

## Frontend checklist before committing

- [ ] Components are named function exports, with a `<Name>Props` interface, in roughly 200
      lines or fewer.
- [ ] Exported components, hooks and functions have a one-line `/** */` comment.
- [ ] Server data comes through `src/api/` hooks, and no component calls `fetch`.
- [ ] No `any`, no TypeScript `enum`s, and type imports use `import type`.
- [ ] State is derived where possible, and server data isn't copied into state.
- [ ] Styles are in a CSS Module using tokens, with no inline styles except runtime values.
- [ ] Loading, error and success states are all handled.
- [ ] Imports use `@/` across folders, with no `../../`.
- [ ] `npm run lint`, `npm run typecheck`, `npm run format:check` and `npm test` pass.
