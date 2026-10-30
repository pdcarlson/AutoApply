"""Worker loop: picks up queued applications and hands them to the agent.

Run with: python -m worker.run
"""
import time
from datetime import datetime

from app.database import Base, SessionLocal, engine
from app.models import IN_PROGRESS, QUEUED, SUBMITTED, Application
from worker.agent import run_application

POLL_SECONDS = 5


def process_next() -> bool:
    """Run the oldest queued application. Returns False if there was nothing to do."""
    db = SessionLocal()
    try:
        application = (db.query(Application)
                       .filter(Application.status == QUEUED)
                       .order_by(Application.created_at)
                       .first())
        if application is None:
            return False

        application.status = IN_PROGRESS
        db.commit()
        print(f"[worker] application {application.id}: {application.url}")

        result = run_application(application.id, application.url)
        application.status = result.status
        application.reason = result.reason
        application.screenshot_path = result.screenshot_path
        if result.status == SUBMITTED:
            application.submitted_at = datetime.now()
        db.commit()
        print(f"[worker] application {application.id} -> {result.status}")
        return True
    finally:
        db.close()


def main():
    Base.metadata.create_all(bind=engine)
    print("[worker] waiting for applications...")
    while True:
        if not process_next():
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
