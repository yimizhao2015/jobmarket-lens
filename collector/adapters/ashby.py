"""Ashby job boards: GET https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true (public posting API)."""
from .common import html_to_text, raw_posting


def collect(company, params, http, max_jobs, stats):
    data = http.get(f"https://api.ashbyhq.com/posting-api/job-board/{params['board']}",
                    params={"includeCompensation": "true"}).json()
    jobs = [j for j in data.get("jobs") or [] if j.get("isListed", True)]
    stats["site_total"] = len(jobs)
    jobs.sort(key=lambda j: j.get("publishedAt") or "", reverse=True)
    for j in jobs[:max_jobs]:
        locs = [j.get("location")] + [s.get("location") for s in j.get("secondaryLocations") or []]
        comp = j.get("compensation") or {}
        yield raw_posting(
            company, j["id"], j.get("jobUrl"), j.get("title"),
            description=j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml")),
            locations=[l for l in locs if l],
            posted_date=(j.get("publishedAt") or "")[:10] or None,
            employment_type=j.get("employmentType"),
            remote_hint=j.get("workplaceType") or ("Remote" if j.get("isRemote") else None),
            pay_text=comp.get("scrapeableCompensationSalarySummary") or comp.get("compensationTierSummary"),
            category=j.get("department") or j.get("team"),
        )
