"""The applicant's profile, which is everything the agent is allowed to put on a form."""
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from agent.applicant.saved_answer import SavedAnswer, normalize
from agent.forms.dates import month_and_year

__all__ = ["Profile", "SavedAnswer", "normalize"]

# Self-ID attribute -> how Claude's facts name it
SELF_ID_FACTS = {
    "gender": "Gender",
    "hispanic_latino": "Hispanic or Latino",
    "race": "Race",
    "veteran": "Protected veteran",
    "disability": "Has a disability",
}
# Keys a saved profile file leaves out when they're empty, so saving never adds a new key
OMITTED_WHEN_EMPTY = ("extra_facts", "middle_name", "school_start", *SELF_ID_FACTS)


def _yes_no(value: bool | None) -> str:
    """Turn True/False/None into the words Claude reads."""
    if value is None:
        return "Unknown (ask the applicant)"
    return "Yes" if value else "No"


@dataclass
class Profile:  # pylint: disable=too-many-instance-attributes  # one field per form question
    """Facts about the applicant, shaped around what application forms ask."""

    first_name: str
    last_name: str
    email: str
    phone: str = ""
    preferred_name: str = ""
    middle_name: str = ""
    city: str = ""
    state: str = ""
    country: str = ""
    linkedin: str = ""
    github: str = ""
    website: str = ""
    resume_path: str = ""
    current_company: str = ""
    current_title: str = ""
    school: str = ""
    degree: str = ""
    major: str = ""
    gpa: str = ""
    graduation: str = ""
    school_start: str = ""  # when the applicant started at school, like "August 2023"
    earliest_start: str = ""
    # None means the applicant hasn't said, so Claude is told to ask
    work_authorized_us: bool | None = True
    needs_sponsorship: bool | None = False
    willing_to_relocate: bool | None = True
    # Voluntary self-ID. "decline" declines every question that has no answer of its own
    eeo: str = "decline"
    # Each is "" (not answered: eeo decides), "decline", or the answer ("Female", "Yes", ...).
    # Race is one of the EEOC categories, like "Asian"
    gender: str = ""
    hispanic_latino: str = ""
    race: str = ""
    veteran: str = ""  # "Yes" means a protected veteran
    disability: str = ""
    answers: list[SavedAnswer] = field(default_factory=list)
    extra_facts: list[str] = field(default_factory=list)  # more lines for Claude to read

    @property
    def full_name(self) -> str:
        """Return the first and last name, for forms with a single Name box (like Ashby)."""
        return " ".join(filter(None, [self.first_name, self.last_name]))

    @property
    def location(self) -> str:
        """Return the city and state, the way location boxes want them."""
        return f"{self.city}, {self.state}" if self.city else ""

    @property
    def school_start_month(self) -> str:
        """Return the month school started, like "August"."""
        return month_and_year(self.school_start)[0]

    @property
    def school_start_year(self) -> str:
        """Return the year school started, like "2023"."""
        return month_and_year(self.school_start)[1]

    @property
    def graduation_month(self) -> str:
        """Return the graduation month, like "May"."""
        return month_and_year(self.graduation)[0]

    @property
    def graduation_year(self) -> str:
        """Return the graduation year, like "2027"."""
        return month_and_year(self.graduation)[1]

    @classmethod
    def load(cls, path) -> "Profile":
        """Read a profile from a JSON file."""
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["answers"] = [SavedAnswer(**answer) for answer in data.get("answers", [])]
        profile = cls(**data)
        # The resume path in the file is relative to the file itself
        if profile.resume_path:
            profile.resume_path = str((path.parent / profile.resume_path).resolve())
        return profile

    def save(self, path) -> None:
        """Write the profile back to a JSON file."""
        data = asdict(self)
        if self.resume_path:
            data["resume_path"] = os.path.relpath(self.resume_path, Path(path).parent)
        for key in OMITTED_WHEN_EMPTY:
            if not data[key]:
                del data[key]
        Path(path).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def saved_answer(self, question: str) -> str | None:
        """Return the saved answer to this question, or None."""
        for saved in self.answers:
            if saved.answers(question):
                return saved.answer
        return None

    def save_answer(self, question: str, answer: str) -> None:
        """Remember an answer so the agent doesn't ask again."""
        self.answers = [saved for saved in self.answers if not saved.answers(question)]
        self.answers.append(SavedAnswer(question, answer))

    def self_id_fact(self, key: str) -> str:
        """Return how Claude reads one self-ID answer."""
        value = getattr(self, key) or ("decline" if self.eeo == "decline" else "")
        if value == "decline":
            return "decline to answer"
        return value or "unknown (ask the applicant)"

    def facts(self) -> str:
        """Return the profile as short lines Claude can read."""
        names = filter(None, [self.first_name, self.middle_name, self.last_name])
        lines = [
            "Name: " + " ".join(names),
            f"Preferred name: {self.preferred_name or self.first_name}",
            f"Email: {self.email}",
            f"Phone: {self.phone}",
            f"Lives in: {self.city}, {self.state}, {self.country}",
            f"LinkedIn: {self.linkedin}",
            f"GitHub: {self.github}",
            f"Website: {self.website}",
            f"Current company: {self.current_company}",
            f"Current title: {self.current_title}",
            f"School: {self.school}",
            f"Degree: {self.degree} in {self.major}",
            f"GPA: {self.gpa}",
            f"Graduation: {self.graduation}",
            f"Started school: {self.school_start or 'unknown'}",
            f"Earliest start date: {self.earliest_start}",
            f"Authorized to work in the United States: {_yes_no(self.work_authorized_us)}",
            f"Needs visa sponsorship now or in the future: {_yes_no(self.needs_sponsorship)}",
            f"Willing to relocate: {_yes_no(self.willing_to_relocate)}",
        ]
        lines += [f"{label}: {self.self_id_fact(key)}" for key, label in SELF_ID_FACTS.items()]
        if self.middle_name:
            lines.insert(1, f"Middle name: {self.middle_name}")
        lines += [f'Saved answer to "{saved.question}": {saved.answer}' for saved in self.answers]
        lines += self.extra_facts
        return "\n".join(lines)
