# AutoApply design files

Colors, fonts and the 12 shared components for the React app. Copy this whole folder into the repo, for example to `frontend/src/design/`, and build every screen from it. The page map (which page lives at which address) is the UI map: `docs/ui-map.md` in the repo, `autoapply-ui-map.md` in the team Drive folder.

## Set up (two lines)

In `main.jsx`:

```js
import './design/tokens.css';
import './design/components.css';
```

Then import components where you need them:

```js
import { PasteBox, StatusPill, QuestionCard } from './design';
```

Light and dark follow the device setting. To force one, put `data-theme="light"` or `data-theme="dark"` on `<html>`.

## What's here

| File | What it is |
|---|---|
| `tokens.css` | Every color, font, spacing, radius and size as a CSS variable, plus the text classes (`aa-display`, `aa-title`, `aa-body`, `aa-body-strong`, `aa-small`, `aa-label`, `aa-mono`). Loads IBM Plex Sans and Mono from Google Fonts |
| `components.css` | Styles for all 12 components. Every class starts with `aa-` |
| `components/*.js` | The components: plain React 18, written with `React.createElement`, so they need no extra build setup. Fine to convert to JSX |
| `index.js` | Exports everything, so you can `import { Button } from './design'` |
| `components.d.ts` | Every component's props, with a comment on each |

## Components

| Component | Use it for |
|---|---|
| `Button` | Every action: `primary`, `secondary`, `quiet`, `danger` |
| `TextField` | Every input, with label, hint and error |
| `Notice` | Inline messages: `info`, `needs`, `error`, `success` |
| `BetaLabel` | "Coming in beta", where a beta feature will live. Never a fake button |
| `PasteBox` | The job-link box at the top of Applications |
| `StatusPill` | Any of the nine statuses (`queued`, `filling`, `needs-you`, `submitted`, `submitted-by-you`, `skipped`, `stopped`, `failed`, `check-before-retrying`) |
| `Sidebar` | The app frame: nav, Needs you count, agent line, sign out, phone menu |
| `StepBar` | The header of the three Setup steps |
| `QuestionCard` | One waiting question on Needs you |
| `ApplicationList` | The list of every application on Applications |
| `StepLog` | An application's steps, live or finished |
| `ProofList` | An application's proof: confirmation, what was sent, resume |

To see all of them, open `autoapply-design/preview/index.html` from the team Drive folder in Chrome. It has a Light/Dark switch at the top. The full usage notes for each one are in the AutoApply design system; ask Paul for the link.

## Rules for code

- **Never write a raw color, font or spacing value.** Use the variables: `color: var(--ink)`, `padding: var(--space-4)`, `border-radius: var(--radius-md)`. Then a change in one place updates the whole app.
- **Amber (`--needs`) only means "the student is needed".** Red (`--danger`) only means failed or delete.
- **Show a status only with `StatusPill`,** never a colored dot or bare text.
- **Each thing has one home.** Before adding a button, check the UI map (`docs/ui-map.md`) for which page owns it. Other pages link there instead of repeating the button.
- **New classes start with `aa-`** and follow the component's name.

## Best-practice evidence (CSCI 4440)

- **#4, coding standards:** add the rules above to the team's coding standards doc.
- **#12, linting:** add Stylelint with `color-no-hex` and `declaration-property-value-disallowed-list` to block raw colors outside `tokens.css`.
- **#14, design patterns:** the nine statuses are a good place for a documented State pattern on the backend, and `StatusPill` is its view.

---

*Drafted with Claude (Opus 5.5 in Claude Code) during Paul's 10/23 design session.*
