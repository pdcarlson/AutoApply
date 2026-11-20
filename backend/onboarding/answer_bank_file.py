"""Stores each user's saved answers in one JSON file."""
import json
import os
import time
from pathlib import Path

REPLACE_ATTEMPTS = 5
REPLACE_RETRY_SECONDS = 0.05


class AnswerBankFile:
    """A JSON file laid out as `{"userdata": {<user>: {<key>: <answer>}}}`."""

    def __init__(self, path: Path | str):
        self.path = Path(path)

    def load_user(self, user: str) -> dict:
        """Return everything saved for the user, or an empty dict."""
        return self._load()["userdata"].get(str(user), {})

    def save_answer(self, user: str, key: str, answer) -> None:
        """Save one answer for the user, replacing any answer under the same key."""
        self.save_answers(user, {key: answer})

    def save_answers(self, user: str, answers: dict) -> None:
        """Merge several answers into what the user already has."""
        data = self._load()
        data["userdata"].setdefault(str(user), {}).update(answers)
        self._save(data)

    def delete_answer(self, user: str, key: str) -> bool:
        """Delete one of the user's answers; return True if there was one."""
        data = self._load()
        answers = data["userdata"].get(str(user))
        if not isinstance(answers, dict) or key not in answers:
            return False
        del answers[key]
        self._save(data)
        return True

    def _load(self) -> dict:
        """Return the whole file, or an empty bank when it doesn't exist yet."""
        if not self.path.exists():
            return {"userdata": {}}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"userdata": {}}
        if not isinstance(data.get("userdata"), dict):
            data["userdata"] = {}
        return data

    def _save(self, data: dict) -> None:
        """Write the whole file."""
        # A temp file swapped in afterwards means a crash never leaves half a bank
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_name(self.path.name + ".tmp")
        try:
            with temp_path.open("w", encoding="utf-8") as file:
                json.dump(data, file, indent=4, ensure_ascii=False)
                file.flush()
                os.fsync(file.fileno())
            self._replace_with(temp_path)
        finally:
            temp_path.unlink(missing_ok=True)

    def _replace_with(self, temp_path: Path) -> None:
        """Move the temp file over the bank file."""
        for attempt in range(REPLACE_ATTEMPTS):
            try:
                temp_path.replace(self.path)
                return
            except PermissionError:
                # Windows refuses the swap while another process briefly has the file open
                if attempt == REPLACE_ATTEMPTS - 1:
                    raise
                time.sleep(REPLACE_RETRY_SECONDS)
