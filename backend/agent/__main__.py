"""Apply to a job from the terminal by running python -m agent <job link> from backend/."""
import argparse

from agent.answers.answerer import Answerer
from agent.answers.claude import ask_claude
from agent.applicant.profile import Profile
from agent.forms import form_for
from agent.jobs.application_log import ApplicationLog, DuplicateLink
from agent.jobs.job_link import JobLink, UnsupportedLink
from agent.runner.apply_run import ApplyRun, RunResult
from agent.settings import PROFILE_PATH, RUNS_DIR, SUBMIT_REAL_FORM, SLOW_MO_MS


def ask(form_field):
    """Ask the applicant one question in the terminal and return their answer."""
    print(f"\n{form_field.label}")
    if form_field.kind == "file":
        return input("Path to the file: ").strip().strip('"')
    if not form_field.options:
        answer = ""
        while not answer:
            answer = input("> ").strip()
        return answer
    for number, option in enumerate(form_field.options, start=1):
        print(f"  {number}. {option}")
    while True:
        choice = input("Pick a number: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(form_field.options):
            return form_field.options[int(choice) - 1]


def main():
    """Parse the link, then run the application until it's filled or sent."""
    parser = argparse.ArgumentParser(description="Fill out a job application from a link.")
    parser.add_argument("url", help="a Greenhouse, Lever or Ashby job link")
    parser.add_argument("--show", action="store_true", help="watch the browser fill the form")
    args = parser.parse_args()

    log = ApplicationLog(RUNS_DIR / "applications.json")
    try:
        link = JobLink.parse(args.url)
        log.add(link)
    except (UnsupportedLink, DuplicateLink) as error:
        print(error)
        return
    try:
        form = form_for(link)
    except UnsupportedLink as error:
        # Lever links are accepted and recorded, but can't be filled yet
        log.update(link, RunResult("failed", str(error)))
        print(error)
        return

    profile = Profile.load(PROFILE_PATH)
    # With SUBMIT_REAL_FORM on, the agent fills the form and keeps the window open for you to
    # check, then presses Submit only after you type "submit" here. The window is shown so you
    # can review it and type any verification code the site emails you.
    runner = ApplyRun(Answerer(profile, ask_claude), RUNS_DIR, submit=False,
                      show=args.show or SUBMIT_REAL_FORM, hold=SUBMIT_REAL_FORM,
                      slow_mo=SLOW_MO_MS)
    print(f"Applying to {link.company} on {link.site.title()} as {profile.first_name} "
          f"{profile.last_name}...")

    result = runner.run(form)
    while result.status == "needs_input":
        print(f"\nThe agent needs {len(result.questions)} answer(s) from you.")
        for form_field in result.questions:
            profile.save_answer(form_field.label, ask(form_field))
        profile.save(PROFILE_PATH)
        result = runner.run(form)

    if result.held is not None:
        result = review_and_submit(result)
    log.update(link, result)
    print_result(result)


def review_and_submit(filled):
    """Show what was filled, press Submit if the applicant says so, and wait for the thank-you page.

    The window is never closed here unless the application was confirmed and screenshotted, or
    the applicant says they're done with it.
    """
    held = filled.held
    print_result(filled)
    print("\nThe form is filled in the open browser window. Check it there before sending.")
    choice = input('Type "submit" to send this application, or press Enter to stop: ')
    if choice.strip().lower() != "submit":
        filled.reason = "Filled in, not sent (you didn't type submit)."
        keep_open_until_done(held)
        return filled

    print("Pressing Submit...")
    sent = held.submit()
    if sent.status != "submitted" and sent.pressed and held.window_open():
        print("\nNo thank-you page yet.")
        if sent.asked_for_code:
            print("The site emailed you a verification code. Type it into the browser window.")
        else:
            print("Finish anything the site asks for in the browser window.")
        print("Waiting for the thank-you page, with no time limit. Ctrl+C stops waiting.")
        try:
            while held.window_open():
                if held.confirmed(timeout_ms=1000):
                    held.save_screenshot(sent)
                    sent.status, sent.reason = "submitted", "The site confirmed the application."
                    break
        except KeyboardInterrupt:
            print("\nStopped waiting.")
        if not held.window_open() and sent.status != "submitted":
            sent.reason = "The form window was closed before the application was confirmed."

    if sent.status == "submitted":
        held.close()  # confirmed, and the screenshot is saved
    else:
        keep_open_until_done(held)
    return sent


def keep_open_until_done(held):
    """Leave the window open until the applicant presses Enter (or closes it themselves)."""
    if held.window_open():
        try:
            input("Not sent or not confirmed yet. The browser window stays open; press Enter "
                  "here when you're done with it (this closes it).")
        except (KeyboardInterrupt, EOFError):
            pass
    held.close()


def print_result(result: RunResult):
    """Show what the agent filled in and how the run ended."""
    print()
    for label, value, source in result.filled:
        print(f"  {label}: {value}  ({source})")
    print(f"\n{result.status.upper()}: {result.reason}")
    if result.screenshot:
        print(f"Screenshot: {result.screenshot}")


if __name__ == "__main__":
    main()
