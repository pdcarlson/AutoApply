# AutoApply UI map

Pages, addresses, navigation and statuses for the React app, from design step 2 (10/23). The full design system is the AutoApply design system artifact; this file is the copy to keep in the repo (for example as docs/ui-map.md).


Every thing in AutoApply has one home: the page where it lives and gets changed. Other pages can show it and link to that home, but they never repeat its buttons. This page gives the page list, the navigation, the home of each thing, and the places where something was tempted to live twice.

**The one rule that settles most cases:** Needs you is for answering questions. Anything you do to a whole application (stop it, skip it, retry it, say you sent it yourself) happens on that application's own page.

## Pages

Three pages sit outside the app frame.

| Page | Address | What it's for |
|---|---|---|
| Sign in | `/signin` | One "Continue with Google" button, one line about what AutoApply does, and a link to the privacy notice. No big marketing header or product screenshot |
| Privacy | `/privacy` | Plain text: what AutoApply keeps, what the agent never does, what the team logs, and how deleting works. No controls |
| Setup | `/setup/resume`, `/setup/profile`, `/setup/questions` | Three steps, once: upload a resume, check the profile, answer the common questions and tick "I certify" once. Finishing opens Applications with the cursor in the paste box. The step bar has the student's email and Sign out |

Everything else is inside the app frame, with a sidebar on a laptop.

| Sidebar item | Address | The one home of |
|---|---|---|
| **Needs you** (count shown only when something waits) | `/needs-you` | Every question the agent is waiting on you to answer |
| **Applications** | `/applications` | The paste-a-link box and the list of every application |
| *(opened from a row)* | `/applications/:id` | One application: what the agent is doing, Stop, Skip, Retry, "I sent it", every step, and the proof |
| **Answer bank** | `/answers` | Every saved answer, including the setup answers and "I certify" |
| **Profile** | `/profile` | Profile fields and the resume |
| **Settings** | `/settings` | Every setting, the privacy record and deleting your data |

Under the sidebar links, one read-only line always says what the agent is doing, such as "Filling Harbor Freight · page 2 of 3 · 3 in line". It links to that application. At the bottom of the sidebar are the student's name and Sign out.

**Where you land.** If you're signed out, you go to Sign in, then back to the page you asked for. If setup isn't finished, you go to Setup at the step you left. If anything is waiting on you, you land on Needs you. Otherwise you land on Applications.

**What the count counts.** It counts the things on Needs you you can act on: question cards, plus the applications waiting on a decision. The same number shows in the sidebar, in the browser tab title ("(3) AutoApply") and in the landing rule, and it updates as soon as you answer.

**On a phone.** Below 768 px the sidebar becomes a top bar with the name, the Needs you count and a Menu button. Needs you is built and tested at 375 px on iPhone Safari and Android Chrome. An application's page is one column, so it's readable on a phone. Everything else is laptop-first.

## The home of each thing

| Thing | Its home | What you can do there | Shown elsewhere (read-only, links home) |
|---|---|---|---|
| Job link to paste | Top of Applications | Paste, then Apply. Apply stays grey until the text looks like a link. The box clears for the next link | Nowhere else |
| Application | Its own page | See status and every step; Stop until it's sent; Skip; Retry a failure; "I sent it" for a blocked one; open the posting | A row in Applications; the "Asked by" line on a question card; the sidebar's agent line |
| Question waiting on you | Needs you | Answer it once. Short answers are saved to the Answer bank automatically, and "Ask me every time" is available | A "2 questions waiting" line on the application's page, with a link |
| Application waiting on a decision (blocked by the site, failed, needs a file AutoApply doesn't have, or check before retrying) | Its own page | Finish it yourself: open the posting, copy the prepared answers, click "I sent it". Or Retry, or Skip | A link-only row on Needs you, under "Applications waiting on a decision" |
| Agent's steps (watching) | The application's page, under Steps | Watch the newest screenshot and line, and scroll back through every step | One status line on the Applications row and in the sidebar's agent line |
| Proof | The application's page, under Proof | The confirmation screenshot; everything that was sent and where each answer came from; the resume used | A Proof link and sent date on the Applications row |
| Saved answer | Answer bank | Edit, delete, set "Ask me every time" | Each Source link in an application's proof opens it here, ready to edit |
| Profile field | Profile | Edit. Unsure fields stay marked until you check them | Source links in proof; an unsure-field card on Needs you opens it here |
| Resume | Profile, at the top | Replace. Re-reading a new resume keeps fields you already fixed | The proof names which resume was sent |
| Privacy notice and "I certify" | Shown once in Setup, then kept on Settings under Agreements, with the date | Read, and see when you agreed | The Privacy page; Answer bank lists "I certify" as a setup answer |
| The 90% cutoff | Settings | Read only for Nov 6: "AutoApply asks when it's less than 90% sure" | Nowhere else |
| Daily limit | Settings | "Coming in beta" label | Nowhere else |
| Delete my data | Settings | "Coming in beta" label | Nowhere else |

## How answering works on Needs you

- **One card per question.** A question gets one card for every application asking it, but only when the wording and the answer choices both match exactly. Otherwise each gets its own card.
- **Each card says why the agent asked:** "No saved answer", "Less than 90% sure" or "Unsure field from your resume". It also lists which applications are waiting on it.
- **Written answers don't merge.** They're company-specific, so each written answer gets its own card for its one application. For Nov 6 the student types it; the card says "AI drafts coming in beta".
- **Unsure profile fields open Profile.** The card opens Profile with that field highlighted and a line naming the applications waiting on it. Saving sends them back in line and links back to Needs you.
- **The agent sends on its own.** Once an application's last question is answered, it goes back in line and the agent sends it. The card names which applications will go out before you save. Stop stays available on each application's page until it's sent.

## Things that wanted two homes, and the pick

| Thing | Where it was tempted to go | Pick | Why |
|---|---|---|---|
| Paste box | Inbox, Applications, a bar on every page | Top of Applications | Pasting creates an application, and the new row shows up right under the box |
| Waiting questions | Inbox table, Needs-you detail page, Applications rows | Needs you only | It has to be the clearest thing while something waits, and one question can belong to several applications |
| Blocked site, "I sent it", Skip | Needs you (mockup), application page | The application's page | Finishing it yourself needs that application's full set of prepared answers. Needs you shows a link row |
| Agent in progress | Inbox "In progress" section, Applications | The application's page | Applications rows and the sidebar line show one read-only status line |
| 90% cutoff | Answer bank slider (mockup), Settings | Settings | All settings in one place |
| Daily limit | Inbox counter (mockup), Settings | Settings, in beta | It's a setting, and it ships in beta |
| Retry | Applications row link (mockup), application page | The application's page | The list stays read-only; its rows only open pages |
| Stop | "Skip this job" on Needs you (mockup), application page | The application's page | Question cards link to the application instead |
| Profile fields | Setup, Profile | Profile | Setup is a one-time guided pass using the same form pieces, and it's never shown again |
| Setup answers and "I certify" | Setup, Answer bank, Settings | Answers in the Answer bank; the agreement record on Settings | Setup fills them once; after that each is changed only in its home |
| Proof | Applications "Screenshot" link (mockup), application page | The application's page | One place to see everything that was sent |
| Sign out | Sidebar, Settings, Setup | Sidebar, plus the Setup step bar | Setup has no sidebar, and the two never show on the same screen |

## Renamed from the Sprint 4 mockup

- **Inbox is gone.** Its parts moved to their homes: the paste box to Applications, waiting items to Needs you, the in-progress list into each application's page and the sidebar's agent line, and the daily limit to Settings. "Inbox" also read like email, which AutoApply doesn't read.
- **Onboarding becomes Setup,** a plainer word, with three steps.
- **Privacy** is new, as a plain page linked from Sign in, Setup and Settings.
- **Needs you, Applications, Answer bank, Profile and Settings keep their names.**

## Safety rules for buttons

- **A link that's already in your list never makes a second application.** The message under the paste box names the job and its status and links to it. Examples: "Already in your list: Northwind · Check before retrying. Open it." and "You applied on Oct 20."
- **"Retry anyway" warns first** on a Check-before-retrying application: "This could send Northwind a second application."
- **"I sent it" and "It went through" can be undone** until you leave the page: "Marked Submitted by you. Undo."

## How each usage pattern moves through it

| Pattern | Path | Clicks |
|---|---|---|
| A. Set up | Sign in, then three Setup steps, ending in the paste box | Linear |
| B. Sign in | Lands on Needs you or Applications | 0 |
| C. Paste a link | Already on Applications when nothing's waiting: paste, Apply, paste the next one | 1 per link |
| D. Answer what's waiting | Lands on Needs you: answer on the card, also on a phone | 1 to 2 per answer |
| E. Finish a blocked application | Needs you row, then the application's page: open the posting, copy answers, "I sent it" | 3 |
| F. Deal with a failure | Needs you row, then the application's page: Retry or Skip | 2 |
| G. Check that a batch went out | The Applications list; open a row for its proof | 0 to 1 |
| H. Look up what was sent | Applications, then the row's Proof link | 1 |
| I. Fix a saved answer | Application's Proof, then that answer's Source link, which opens it in the Answer bank to edit | 2 |
| J. Replace the resume | Profile, then Replace resume | 2 |
| K. Stop an application | The "Added" message under the paste box, or the row, then Stop | 2 |
| L. Watch the agent | The sidebar's agent line, then Steps | 1 |
| M. Change a setting | Settings | 1 |

## "Coming in beta" spots for the Nov 6 demo

Each label sits exactly where the feature will live, as plain text with no button.

- **Applications list header:** filters and CSV export.
- **Written-answer cards on Needs you:** "AI drafts coming in beta".
- **Answer bank:** "Matching differently worded questions coming in beta".
- **Blocked Greenhouse applications:** "Pasting Greenhouse's emailed code coming in beta".
- **Settings:** daily limit; delete my data.

The job feed, fit ranking and email alerts come later, so they get no spot at all yet.

## The nine statuses and where they show

Every application has exactly one status, shown as a word plus a symbol, never by color alone. Applications rows, the sidebar's agent line and the application's page all use the same word.

| Status | Means | What the student can do on the application's page |
|---|---|---|
| Queued | Waiting its turn on the server | Stop |
| Filling | The agent is working, and Steps updates live | Stop, watch |
| Needs you | Waiting on a question or a decision | Stop; answer on Needs you; or finish it yourself if it's blocked |
| Submitted | Sent, with confirmation proof | See proof |
| Submitted by you | You finished it on the company's site, so there's no confirmation screenshot | See what the agent prepared; Undo right after marking it |
| Skipped | You chose not to finish it | Retry |
| Stopped | You stopped it before it was sent | Retry |
| Failed (safe to retry) | It never got to submit | Retry, Skip |
| Check before retrying | It clicked submit but never saw a confirmation | "It went through" (check your email or the posting first), or "Retry anyway" with a warning |

## For the team

- These pages and addresses are what the React routes and the use-case steps should follow from now on. The walkthrough video can use them too.
- The questions from this step are in the IMMEDIATE TODO tab.

---

*Drafted with Claude (Opus 5.5 in Claude Code) during Paul's 10/23 design session.*
