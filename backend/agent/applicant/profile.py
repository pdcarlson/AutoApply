"""The applicant's profile, which is everything the agent is allowed to put on a form."""
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path


def normalize(question):
    """Lowercase a question and drop extra spaces so the same question always matches."""
    return " ".join(question.lower().split()).rstrip("*").strip()


def yes_no(value):
    """Turn True/False/None into the words Claude reads."""
    if value is None:
        return "Unknown (ask the applicant)"
    return "Yes" if value else "No"


@dataclass
class SavedAnswer:
    """An answer the applicant already gave to a form question."""

    question: str
    answer: str


@dataclass
class Profile:  # pylint: disable=too-many-instance-attributes
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
    earliest_start: str = ""
    # None means the applicant hasn't said, so Claude is told to ask
    work_authorized_us: bool | None = True
    needs_sponsorship: bool | None = False
    willing_to_relocate: bool | None = True
    eeo: str = "decline"
    answers: list[SavedAnswer] = field(default_factory=list)
    extra_facts: list[str] = field(default_factory=list)  # more lines for Claude to read

    @property
    def full_name(self):
        """Return the whole name, for forms with one name box (Lever)."""
        return " ".join(filter(None, [self.first_name, self.middle_name, self.last_name]))

    @property
    def location(self):
        """Return the city and state, the way location boxes want them."""
        return f"{self.city}, {self.state}" if self.city else ""

    @classmethod
    def load(cls, path):
        """Read a profile from a JSON file."""
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["answers"] = [SavedAnswer(**answer) for answer in data.get("answers", [])]
        profile = cls(**data)
        # The resume path in the file is relative to the file itself
        if profile.resume_path:
            profile.resume_path = str((path.parent / profile.resume_path).resolve())
        return profile

    def save(self, path):
        """Write the profile back to a JSON file."""
        data = asdict(self)
        if self.resume_path:
            data["resume_path"] = os.path.relpath(self.resume_path, Path(path).parent)
        # Leave the key out when unused, so saving never adds a new key to a profile file
        if not self.extra_facts:
            del data["extra_facts"]
        if not self.middle_name:
            del data["middle_name"]
        Path(path).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def saved_answer(self, question):
        """Return the saved answer to this question, or None."""
        for saved in self.answers:
            if normalize(saved.question) == normalize(question):
                return saved.answer
        return None

    def save_answer(self, question, answer):
        """Remember an answer so the agent doesn't ask again."""
        self.answers = [saved for saved in self.answers
                        if normalize(saved.question) != normalize(question)]
        self.answers.append(SavedAnswer(question, answer))

    def facts(self):
        """Return the profile as short lines Claude can read."""
        lines = [
            "Name: " + " ".join(filter(None, [self.first_name, self.middle_name, self.last_name])),
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
            f"Earliest start date: {self.earliest_start}",
            f"Authorized to work in the United States: {yes_no(self.work_authorized_us)}",
            f"Needs visa sponsorship now or in the future: {yes_no(self.needs_sponsorship)}",
            f"Willing to relocate: {yes_no(self.willing_to_relocate)}",
            "Demographic questions (gender, race, veteran, disability): "
            + ("decline to answer" if self.eeo == "decline" else "ask the applicant"),
        ]
        if self.middle_name:
            lines.insert(1, f"Middle name: {self.middle_name}")
        lines += [f'Saved answer to "{saved.question}": {saved.answer}' for saved in self.answers]
        lines += self.extra_facts
        return "\n".join(lines)
