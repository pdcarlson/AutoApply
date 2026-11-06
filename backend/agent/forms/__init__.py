"""One form class per applicant tracking system."""
from agent.forms.greenhouse_form import GreenhouseForm
from agent.jobs.job_link import UnsupportedLink


def form_for(link):
    """Return the form class for the link's site."""
    if link.site == "greenhouse":
        return GreenhouseForm(link)
    raise UnsupportedLink(f"AutoApply can't fill {link.site.title()} forms yet.")
