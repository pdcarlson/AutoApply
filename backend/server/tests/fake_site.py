"""Routes the test postings at fakecompany to the local fake forms, so tests never go online."""
import json

from agent.forms import form_for as real_form_for
from agent.forms.ashby_form import AshbyForm
from agent.forms.base_form import AtsForm
from agent.forms.greenhouse_form import GreenhouseForm
from agent.jobs.job_board import AshbyBoard, GreenhouseBoard, JobBoard
from agent.jobs.job_link import JobLink
from server.config import BACKEND_DIR

FAKE_FORMS = BACKEND_DIR / "agent" / "tests" / "fake_forms"
FAKE_COMPANY = "fakecompany"
# Only these exact test postings map to the local fake forms. Any other link, including
# fakecompany with another job id, is treated as a real posting.
FAKE_JOB_IDS = {
    "greenhouse": frozenset({"1001", "1002"}),
    "ashby": frozenset({"00000000-0000-4000-8000-000000001001"}),
}


def is_fake(link: JobLink) -> bool:
    """Return True for the test postings that map to the local fake forms."""
    return link.company.lower() == FAKE_COMPANY and link.job_id in FAKE_JOB_IDS.get(link.site, ())


def fake_job_data(site: str = "greenhouse") -> dict:
    """Return the saved API payload of the fake posting on `site`."""
    return json.loads((FAKE_FORMS / f"{site}_api.json").read_text(encoding="utf-8"))


def form_for(link: JobLink, real=real_form_for) -> AtsForm:
    """Return the local fake form for a test posting, or `real(link)` for any other link."""
    if not is_fake(link):
        return real(link)
    form_class = AshbyForm if link.site == "ashby" else GreenhouseForm
    return form_class(link, job_data=fake_job_data(link.site),
                      url=(FAKE_FORMS / f"{link.site}_form.html").resolve().as_uri())


def fake_boards() -> list[JobBoard]:
    """Return job boards that list the fake Greenhouse and Ashby postings, from local files."""
    ashby = fake_job_data("ashby")
    return [GreenhouseBoard(FAKE_COMPANY, data={"jobs": [fake_job_data("greenhouse")]}),
            AshbyBoard(FAKE_COMPANY, data={"jobs": [{**ashby, "location": ashby["locationName"]}]})]
