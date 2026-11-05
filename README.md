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
