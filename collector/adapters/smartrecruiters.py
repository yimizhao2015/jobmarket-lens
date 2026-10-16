"""SmartRecruiters public Posting API (Visa), and SmartRecruiters-hosted career sites (collect_site)."""
import re

import requests
from bs4 import BeautifulSoup

from .common import html_to_text, raw_posting, seen_before

API = "https://api.smartrecruiters.com/v1/companies/{cid}/postings"


def collect(company, params, http, max_jobs, stats):
    cid = params["company_id"]
    offset, seen = 0, 0
    while seen < max_jobs:
        data = http.get(API.format(cid=cid), params={"limit": 100, "offset": offset}).json()
        if offset == 0:
            stats["site_total"] = data.get("totalFound")
        items = data.get("content") or []
        if not items:
            break
        for p in items:
            rec = seen_before(company, http, source_id=p.get("refNumber") or p["id"])
            if rec:  # already in the history: no detail request
                yield rec
                seen += 1
                if seen >= max_jobs:
                    return
                continue
            d = http.get(API.format(cid=cid) + "/" + p["id"]).json()
            sec = (d.get("jobAd") or {}).get("sections") or {}
            desc = "\n".join(filter(None, [html_to_text((sec.get(k) or {}).get("text"))
                                           for k in ("companyDescription", "jobDescription", "qualifications", "additionalInformation")]))
            loc = p.get("location") or {}
            loc_s = ", ".join(filter(None, [loc.get("city"), loc.get("region"), (loc.get("country") or "").upper()]))
            remote = "Remote" if loc.get("remote") else ("Hybrid" if loc.get("hybrid") else None)
            yield raw_posting(
                company, p.get("refNumber") or p["id"], d.get("postingUrl") or f"https://jobs.smartrecruiters.com/{cid}/{p['id']}",
                p.get("name"),
                description=desc or None,
                locations=[loc_s] if loc_s else [],
                posted_date=(p.get("releasedDate") or "")[:10] or None,
                employment_type=(p.get("typeOfEmployment") or {}).get("label"),
                remote_hint=remote,
                category=(p.get("function") or {}).get("label") or (p.get("department") or {}).get("label"),
                level_hint=(p.get("experienceLevel") or {}).get("label"),
            )
            seen += 1
            if seen >= max_jobs:
                return
        offset += len(items)


def collect_site(company, params, http, max_jobs, stats):
    """The company's SmartRecruiters career site, for companies whose Posting API is closed to crawlers by
    api.smartrecruiters.com/robots.txt. careers.smartrecruiters.com/{cid}?search=%20 lists every location group
    (groups over nine jobs continue through /{cid}/api/more); each job page carries schema.org microdata."""
    cid = params["company_id"]
    base = f"https://careers.smartrecruiters.com/{cid}"
    job_re = re.compile(rf'href="(https://jobs\.smartrecruiters\.com/{re.escape(cid)}/(\d+)[^"]*)"')
    soup_html = http.get(base, params={"search": " "}).text
    urls = dict((m.group(2), m.group(1)) for m in job_re.finditer(soup_html))
    soup = BeautifulSoup(soup_html, "html.parser")
    for more in soup.select("a.js-more[data-type][data-value]"):
        page = int(more.get("data-page") or 0) + 1
        while True:
            chunk = http.get(f"{base}/api/more", params={"search": " ", "type": more["data-type"],
                                                         "value": requests.utils.unquote(more["data-value"]), "page": page}).text
            found = {m.group(2): m.group(1) for m in job_re.finditer(chunk)}
            if not found.keys() - urls.keys():
                break
            urls.update(found)
            page += 1
    stats["site_total"] = len(urls)
    # Job ids grow over time, so the highest ids are the newest postings.
    seen = 0
    for jid in sorted(urls, key=int, reverse=True):
        url = urls[jid]
        rec = seen_before(company, http, source_id=jid)
        if rec:  # already in the history: no detail request
            yield rec
            seen += 1
            if seen >= max_jobs:
                return
            continue
        try:
            page = BeautifulSoup(http.get(url).text, "html.parser")
        except requests.HTTPError:
            stats["gone"] = stats.get("gone", 0) + 1
            continue

        def prop(name):
            el = page.select_one(f'[itemprop="{name}"]')
            return (el.get("content") or el.get_text(" ", strip=True)) if el else None

        desc = "\n".join(filter(None, (html_to_text(str(el)) for name in ("description", "responsibilities", "qualifications", "incentives")
                                       for el in page.select(f'[itemprop="{name}"]'))))
        loc = ", ".join(filter(None, [prop("addressLocality"), prop("addressRegion"), prop("addressCountry")]))
        yield raw_posting(
            company, jid, url.split("?")[0], prop("title"),
            description=desc or None,
            locations=[loc] if loc else [],
            posted_date=(prop("datePosted") or "")[:10] or None,
            employment_type=prop("employmentType"),
            category=prop("industry"),
            source_method="html",
        )
        seen += 1
        if seen >= max_jobs:
            return
