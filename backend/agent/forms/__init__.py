"""One form class per applicant tracking system."""
from agent.forms.ashby_form import AshbyForm
from agent.forms.base_form import AtsForm
from agent.forms.greenhouse_form import GreenhouseForm
from agent.jobs.job_link import JobLink, Site, UnsupportedLink

FORMS = {Site.GREENHOUSE: GreenhouseForm, Site.ASHBY: AshbyForm}


def form_for(link: JobLink) -> AtsForm:
    """Return the form for the link's site, or raise UnsupportedLink if it can't be filled."""
    if link.site in FORMS:
        return FORMS[link.site](link)
    raise UnsupportedLink(f"AutoApply can't fill {link.site.title()} forms yet.")
