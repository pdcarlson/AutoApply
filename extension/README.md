# AutoApply Filler (Chrome extension)

Fills a job application in your own browser with the answers AutoApply prepared. You check the
form and press Submit yourself. It exists because Lever turns applications from the agent's
browser away, and the agent never tries to get past a site's bot check.

Works on Lever (`jobs.lever.co`) for now.

## Install (once)

1. Open `chrome://extensions` in Chrome.
2. Turn on **Developer mode** (top right).
3. Press **Load unpacked** and pick this `extension/` folder.

## Use

1. Start AutoApply (the backend has to be running on `localhost:8080`).
2. Add the job in the AutoApply Inbox and answer the questions it asks, so the answers exist.
3. Open the job's application form in Chrome (the link ending in `/apply`).
4. Press **Fill in my answers** in the AutoApply panel at the bottom right.
5. Check the form. The panel lists anything it couldn't fill and anything that's yours to do.
6. Press Submit yourself. When Lever's thank-you page shows, the application is recorded in
   AutoApply.

## What it does and doesn't do

- It only reads from, and reports to, AutoApply on your own computer.
- It never presses Submit and never touches a CAPTCHA.
- It never fills sign-in, password or Social Security number fields.

## Files

- `content.js`: the panel on the page, and telling AutoApply when the thank-you page shows.
- `fill.js`: puts the answers into the form. No Chrome APIs, so tests load it into a plain page.
- `background.js`: talks to the local AutoApply server.
