"""Apply to a job from the terminal by running python -m agent <job link> from backend/."""
import argparse

from agent.answers.answerer import Answerer
from agent.answers.claude import ask_claude
from agent.applicant.profile import Profile
from agent.forms import form_for
from agent.jobs.application_log import ApplicationLog, DuplicateLink
from agent.jobs.job_link import JobLink, UnsupportedLink
from agent.runner.apply_run import ApplyRun, RunResult
from agent.settings import PROFILE_PATH, RUNS_DIR, SUBMIT_REAL_FORM


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
        # Lever and Ashby links are accepted and recorded, but can't be filled yet
        log.update(link, RunResult("failed", str(error)))
        print(error)
        return

    profile = Profile.load(PROFILE_PATH)
    runner = ApplyRun(Answerer(profile, ask_claude), RUNS_DIR,
                      submit=SUBMIT_REAL_FORM, show=args.show)
    print(f"Applying to {link.company} on {link.site.title()} as {profile.first_name} "
          f"{profile.last_name}...")

    result = runner.run(form)
    while result.status == "needs_input":
        print(f"\nThe agent needs {len(result.questions)} answer(s) from you.")
        for form_field in result.questions:
            profile.save_answer(form_field.label, ask(form_field))
        profile.save(PROFILE_PATH)
        result = runner.run(form)

    log.update(link, result)
    print_result(result)


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
