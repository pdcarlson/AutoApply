"""One form class per applicant tracking system."""
from agent.forms.ashby_form import AshbyForm
from agent.forms.greenhouse_form import GreenhouseForm
from agent.jobs.job_link import UnsupportedLink

FORMS = {"greenhouse": GreenhouseForm, "ashby": AshbyForm}


def form_for(link):
    """Return the form class for the link's site."""
    if link.site in FORMS:
        return FORMS[link.site](link)
    raise UnsupportedLink(f"AutoApply can't fill {link.site.title()} forms yet.")
