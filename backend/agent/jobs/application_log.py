"""A record of every job the agent has worked on, kept in a JSON file until we have a database."""
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path


class DuplicateLink(ValueError):
    """The applicant already applied to this job."""


class ApplicationLog:
    """Creates and updates one application record per job."""

    def __init__(self, path):
        self.path = Path(path)
        if self.path.exists():
            self.records = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.records = []

    def find(self, link):
        """Return the record for this job, or None."""
        for record in self.records:
            if (record["site"], record["company"], record["job_id"]) == \
                    (link.site, link.company, link.job_id):
                return record
        return None

    def add(self, link):
        """Create a record for a new job. Raises DuplicateLink if it was already submitted."""
        record = self.find(link)
        if record and record["status"] == "submitted":
            raise DuplicateLink(f"You already applied to this job on {record['updated_at'][:10]}.")
        if record is None:
            record = asdict(link)
            self.records.append(record)
        self.set_status(record, "started", "")

    def update(self, link, result):
        """Save what happened on the latest run."""
        record = self.find(link)
        self.set_status(record, result.status, result.reason)
        record["screenshot"] = result.screenshot

    def set_status(self, record, status, reason):
        """Change a record's status and write the log to disk."""
        record["status"] = status
        record["reason"] = reason
        record["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.records, indent=2) + "\n", encoding="utf-8")
