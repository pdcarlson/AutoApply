# Auto Apply — wireframe-style prototype

A clickable prototype of Auto Apply (sign in, resume setup, Inbox, Applications,
Profile, Answer bank, Settings). All data is in-memory sample data; nothing is sent
anywhere.

## Run it

    cd dist
    python3 -m http.server 8000      # any static server works
    # open http://localhost:8000/#welcome

`dist/` is the finished app: `index.html` + `assets/app.js` (one self-contained
bundle: React, state store, styles). The Lato font loads from Google Fonts.
Routes are hash-based: `#welcome`, `#upload`, `#review`, `#questions`, `#inbox`,
`#applications`, `#contact` (profile), `#answers`, `#controls` (settings), `#deleted`.

`dist/artifact-page.html` is the exact page published as the Claude artifact
(the artifact host adds the doctype/head around it).

## Important: there is no original source here

`build/original-bundle.js` is the **compiled Vite/React build** of the earlier
version. The original component source was not available, so every change since
was made by patching that bundle. Component names are minified (e.g. `ea` = Inbox
page, `vi` = Applications, `Fa` = Answer bank, `qa` = Profile page, `va` = Check
profile, `Sa` = Resume upload, `la` = Common questions, `Da` = Sign-in, `to` =
left sidebar, `uo` = app root, `j` = zustand store hook, `M()` = store actions).

## How `dist/assets/app.js` is produced

    python3 build/transform.py

reads `build/original-bundle.js`, applies every change, and writes
`dist/assets/app.js`. It is deterministic (re-running reproduces the shipped file
byte for byte). Each step is an exact string replacement that fails loudly if its
target text isn't found.

| File | What it does |
|---|---|
| `build/transform.py` | Layout changes: left sidebar nav, Inbox filters inline, single-page Profile, setup header, sign-in page, light theme by default, list-only Inbox, phone section picker. Also swaps the color tokens, squares off corner radii, and injects `overrides.css`. Runs `patch2.py` and `patch3.py`. |
| `build/patch2.py` | Removes walkthrough/story tags; setup pages scroll with the continue button inline; Sign out in setup header; Links, multi-education, dated experience, Description bullets, Additional information (custom fields); date picker for earliest start; copy edits. |
| `build/patch3.py` | Full address fields in Contact; landing/Inbox copy trims. |
| `build/overrides.css` | The wireframe visual style (sidebar, tables, pills, buttons, checkboxes, setup pages, responsive rules). |
| `build/tokens_light.css`, `build/tokens_dark.css` | Grayscale color + type tokens for light and dark mode. |

## Suggested next step for Claude Code

The patch-on-a-bundle setup works but is awkward to extend. A good first task is
to rebuild this as a normal React + Vite project with readable components, using
`dist/` as the visual and behavioral reference (run it side by side and match
each screen). The store logic (job states, agent tick/queue, confidence threshold,
answer matching, daily limit) lives near the top of the app section of the bundle
and is worth porting first.

## Known gaps

- New profile data (links, address, multiple schools, custom fields, dated
  experience) is stored and editable but the sample application forms still fill
  from the original fixed sample values.
- Lever is removed from the landing-page copy only; Lever links and sample jobs
  still work.
