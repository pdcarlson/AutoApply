"""Reads a job link and works out which site it's on."""
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlsplit

SITES = {
    "boards.greenhouse.io": "greenhouse",
    "job-boards.greenhouse.io": "greenhouse",
    "jobs.lever.co": "lever",
    "jobs.ashbyhq.com": "ashby",
}


class UnsupportedLink(ValueError):
    """The link isn't a job on a site AutoApply supports."""


@dataclass
class JobLink:
    """One job posting, identified by its site, company and job id."""

    url: str
    site: str
    company: str
    job_id: str
    # The link exactly as the user pasted it. The agent opens this page, so tracking tags
    # like ?jr_id=... reach the site. `url` is the cleaned-up link used to spot duplicates.
    pasted: str = field(default="", compare=False)

    @classmethod
    def parse(cls, url):
        """Return the JobLink for a Greenhouse, Lever or Ashby link, or raise UnsupportedLink."""
        parts = urlsplit(url.strip())
        host = (parts.hostname or "").lower()
        site = SITES.get(host)
        if site is None:
            raise UnsupportedLink(
                f"AutoApply only takes Greenhouse, Lever and Ashby job links, not {host or url}.")
        path = [part for part in parts.path.split("/") if part]

        if site == "greenhouse":
            company, job_id = greenhouse_ids(path, parts.query)
            # boards.greenhouse.io redirects to job-boards, so both hosts mean the same job
            return cls(f"https://job-boards.greenhouse.io/{company}/jobs/{job_id}",
                       site, company, job_id, pasted=url.strip())

        # jobs.lever.co/<company>/<id>[/apply] and jobs.ashbyhq.com/<company>/<id>[/application]
        if len(path) < 2:
            raise UnsupportedLink(f"{url} doesn't point at a single job.")
        return cls(f"https://{host}/{path[0]}/{path[1]}", site, path[0], path[1],
                   pasted=url.strip())


def greenhouse_ids(path, query):
    """Return the company and job id from a Greenhouse job link or embed link."""
    if path[:2] == ["embed", "job_app"]:
        params = parse_qs(query)
        company = params.get("for", [""])[0]
        job_id = params.get("token", [""])[0]
    elif len(path) >= 3 and path[1] == "jobs":
        company, job_id = path[0], path[2]
    else:
        company, job_id = "", ""
    if not company or not job_id.isdigit():
        raise UnsupportedLink("That Greenhouse link doesn't point at a single job.")
    return company, job_id
