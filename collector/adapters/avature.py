"""Avature career portals (MetLife). The portal's sitemap lists the JobDetail pages; a page carries schema.org
JobPosting JSON-LD on some portals and always the posting's labeled fields ("Posted Date", "Location", ...)
in its detail articles, which fill whatever the JSON-LD leaves out.
params: sitemap (the portal's sitemap index, from its robots.txt), url_pattern (JobDetail pages in one language)."""
import re

import requests
from bs4 import BeautifulSoup

from .common import find_jobposting_jsonld, html_to_text, jobposting_to_raw, raw_posting
from .html_sites import _sitemap_entries, _text
from .successfactors import _parse_date


def _field(text, *labels):
    for lab in labels:
        m = re.search(rf"(?:^|\n){lab}\s*:?\s*\n([^\n]{{1,120}})", text, re.I)
        if m:
            return m.group(1).strip()
    return None


def _detail(company, jid, url, page):
    soup = BeautifulSoup(page, "html.parser")
    arts = soup.select(".article--details")
    fields = "\n".join(a.get_text("\n", strip=True) for a in arts)
    # The description is the article headed "Description ..." (or the longest one when none is headed so).
    desc = [a for a in arts if re.match(r"\s*(Job )?Description", a.get_text(" ", strip=True), re.I)]
    desc = desc or sorted(arts, key=lambda a: len(a.get_text()), reverse=True)[:1]
    desc_text = "\n".join(filter(None, (html_to_text(str(a)) for a in desc))) or None
    loc = _field(fields, "Location", "Job Location", "Primary Location", "City")
    jp = find_jobposting_jsonld(page)
    if jp:
        rec = jobposting_to_raw(company, jid, url, jp)
        rec["description"] = rec["description"] or desc_text
        rec["locations"] = rec["locations"] or ([loc] if loc else [])
        rec["remote_hint"] = rec["remote_hint"] or _field(fields, "Work Arrangement", "Workplace Type")
        return rec
    title = soup.title.get_text(strip=True).split(" - ")[0].strip() if soup.title else None
    return raw_posting(company, _field(fields, "Job ID", "Requisition ID") or jid, url, title,
                       description=desc_text, locations=[loc] if loc else [],
                       posted_date=_parse_date(_field(fields, "Posted Date", "Date Posted", "Posting Date")),
                       employment_type=_field(fields, "Working Schedule", "Time Type", "Employment Type", "Job Type"),
                       remote_hint=_field(fields, "Work Arrangement", "Workplace Type"),
                       source_method="html")


def collect(company, params, http, max_jobs, stats):
    pattern = params.get("url_pattern", r"/JobDetail/")
    entries = {u: m for u, m in _sitemap_entries(http, params["sitemap"]) if re.search(pattern + r".*/\d+/?$", u)}
    urls = sorted(entries, key=lambda u: entries[u] or "", reverse=True)
    stats["site_total"] = len(urls)
    seen = 0
    for url in urls:
        jid = re.search(r"/(\d+)/?$", url).group(1)
        try:
            rec = _detail(company, jid, url, _text(http.get(url)))
        except requests.HTTPError:  # closed since the sitemap was written
            stats["gone"] = stats.get("gone", 0) + 1
            continue
        if not rec.get("posted_date"):  # postings without a date are left out downstream anyway
            stats["no_date"] = stats.get("no_date", 0) + 1
            continue
        yield rec
        seen += 1
        if seen >= max_jobs:
            return
