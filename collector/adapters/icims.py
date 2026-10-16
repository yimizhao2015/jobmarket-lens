"""iCIMS career portals (careers-{name}.icims.com). The portal's sitemap lists every open job page; the page
content is served inside an iframe (?in_iframe=1) that carries schema.org JobPosting JSON-LD."""
import re

import requests

from .common import find_jobposting_jsonld, jobposting_to_raw, seen_before
from .html_sites import _sitemap_entries, _text


def collect(company, params, http, max_jobs, stats):
    seen = 0
    for host in params.get("hosts") or [params["host"]]:
        entries = {u: m for u, m in _sitemap_entries(http, f"https://{host}/sitemap.xml")
                   if re.search(r"/jobs/\d+/", u)}
        urls = sorted(entries, key=lambda u: entries[u] or "", reverse=True)
        stats["site_total"] = stats.get("site_total", 0) + len(urls)
        for url in urls:
            jid = re.search(r"/jobs/(\d+)/", url).group(1)
            rec = seen_before(company, http, source_id=jid)
            if rec:  # already in the history: no detail request
                yield rec
                seen += 1
                if seen >= max_jobs:
                    return
                continue
            try:
                jp = find_jobposting_jsonld(_text(http.get(url, params={"in_iframe": 1})))
            except requests.HTTPError:  # closed since the sitemap was written
                stats["gone"] = stats.get("gone", 0) + 1
                continue
            if not jp:
                stats["no_jobposting"] = stats.get("no_jobposting", 0) + 1
                continue
            yield jobposting_to_raw(company, jid, url, jp)
            seen += 1
            if seen >= max_jobs:
                return
