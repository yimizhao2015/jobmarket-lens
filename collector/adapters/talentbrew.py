"""TalentBrew (Radancy) career sites whose job pages carry no JSON-LD (Disney). The site's sitemap lists every job
page (/job/{city}/{title}/{company id}/{job id}); the page shows the posting's fields in TalentBrew's standard
markup: h1, .job-date ("Date posted Oct. 15, 2026"), .job-location, .job-id and .ats-description.
Sites whose job pages do carry JSON-LD use jsonld_sitemap instead."""
import re

import requests
from bs4 import BeautifulSoup

from .common import find_jobposting_jsonld, html_to_text, jobposting_to_raw, raw_posting
from .html_sites import _sitemap_entries, _text
from .successfactors import _parse_date


def _value(soup, sel, label):
    el = soup.select_one(sel)
    if not el:
        return None
    return re.sub(rf"^\s*{label}\s*:?\s*", "", el.get_text(" ", strip=True), flags=re.I) or None


def collect(company, params, http, max_jobs, stats):
    pattern = params.get("url_pattern", r"/job/")
    entries = {u: m for u, m in _sitemap_entries(http, params["sitemap"]) if re.search(pattern, u)}
    urls = sorted(entries, key=lambda u: entries[u] or "", reverse=True)
    stats["site_total"] = len(urls)
    seen = 0
    for url in urls:
        jid = (re.search(r"/(\d+)/?$", url) or [None, url])[1]
        try:
            page = _text(http.get(url))
        except requests.HTTPError:  # closed since the sitemap was written
            stats["gone"] = stats.get("gone", 0) + 1
            continue
        jp = find_jobposting_jsonld(page)
        if jp:
            yield jobposting_to_raw(company, jid, url, jp)
        else:
            soup = BeautifulSoup(page, "html.parser")
            h1 = soup.select_one("h1")
            desc = soup.select_one(".ats-description")
            loc = _value(soup, ".job-location", "Location")
            yield raw_posting(company, _value(soup, ".job-id", "Job ID") or jid, url, h1.get_text(" ", strip=True) if h1 else None,
                              description=html_to_text(str(desc)) if desc else None,
                              locations=[re.sub(r"\s+", " ", loc)] if loc else [],
                              posted_date=_parse_date((_value(soup, ".job-date", "Date posted") or "").replace("Sept", "Sep")),
                              source_method="html")
        seen += 1
        if seen >= max_jobs:
            return
