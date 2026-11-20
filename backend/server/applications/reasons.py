"""The wording that tells the person why a job waits for them in `handoff`."""
from agent.runner.apply_run import RunResult
from server.config import Config

WATCHING_CODE = ("{site} emailed you a verification code to finish this application. Find "
                 "the email and enter the code here: the agent types it into the form and "
                 "submits it.")
WATCHING = ("The agent pressed Submit but hasn't seen a confirmation page yet. The form window "
            "stays open: finish it there — the agent will record the application as soon as "
            "the thank-you page appears.")
WATCHING_CAPTCHA = ("{site} showed a CAPTCHA after Submit, and the agent never solves those. "
                    "Solve it in the open form window: the agent will record the application "
                    "as soon as the thank-you page appears.")
HIDDEN_WINDOW = (" (The agent's browser is hidden because AGENT_SHOW_BROWSER is off: check your "
                 "email and the site, then mark it submitted.)")
WINDOW_CLOSED = ("The form window was closed before the application was confirmed. Check your "
                 "email and the site: if it went through, mark it submitted.")
UNCONFIRMED = ("The agent pressed Submit but didn't see a confirmation page. Check the site "
               "before trying again.")
PROTECTED_WINDOW = (" The agent filled in the rest and left the form window open: finish that "
                    "step there and press Submit. The agent will record the application as "
                    "soon as the thank-you page appears.")
PROTECTED_HIDDEN = (" (The agent's browser is hidden because AGENT_SHOW_BROWSER is off: open the "
                    "job link, finish the form there, then mark it submitted.)")


def watching_reason(job: dict, config: Config, result: RunResult | None) -> str:
    """Return why the job is in `handoff` while its open window is watched for the confirmation.

    An emailed code or a CAPTCHA that the submit ran into gets its own wording.
    """
    site = job.get("ats") or "The site"
    if result is not None and result.asked_for_code:
        # The code is typed in through the app, so a hidden browser doesn't matter.
        return WATCHING_CODE.format(site=site)
    if result is not None and result.protected:
        reason = WATCHING_CAPTCHA.format(site=site)
    else:
        reason = WATCHING
    return reason if config.show_browser else reason + HIDDEN_WINDOW


def protected_reason(config: Config, result: RunResult) -> str:
    """Return why the job is in `handoff` after a fill that left a protected step alone."""
    return result.reason + (PROTECTED_WINDOW if config.show_browser else PROTECTED_HIDDEN)
