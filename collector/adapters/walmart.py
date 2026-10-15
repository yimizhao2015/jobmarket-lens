"""Walmart careers (careers.walmart.com, a Next.js front end over Workday).

Walmart's Workday CXS endpoint answers HTTP 422 to every list request, and /results and /api are
disallowed in robots.txt. The site's sitemap lists every job page; each page embeds the full
requisition in __NEXT_DATA__. Requisition ids rise over time, so the newest are read first.
"""
import json
import re

from .common import html_to_text, raw_posting
from .html_sites import _text

SITEMAP = "https://careers.walmart.com/sitemap.xml"
NEXT_RE = re.compile(r'<script id="?__NEXT_DATA__"?[^>]*>(.*?)</script>', re.S)


def _v(x):
    return x.get("value") if isinstance(x, dict) else x


def collect(company, params, http, max_jobs, stats):
    xml = http.get(SITEMAP).text
    urls = sorted(set(re.findall(r"<loc>(https://careers\.walmart\.com/us/en/jobs/R-(\d+))</loc>", xml)),
                  key=lambda u: -int(u[1]))
    stats["site_total"] = len(urls)
    seen = 0
    for url, _ in urls:
        m = NEXT_RE.search(_text(http.get(url)))
        if not m:
            stats["no_data"] = stats.get("no_data", 0) + 1
            continue
        d = json.loads(m.group(1))["props"]["pageProps"].get("jobDetails") or {}
        if _v(d.get("requisitionStatus")) not in (None, "Open") and (d.get("requisitionStatus") or {}).get("id") != "OPEN":
            stats["not_open"] = stats.get("not_open", 0) + 1
            continue
        locs = []
        for loc in [d.get("primaryLocation")] + list(d.get("additionalLocations") or []):
            if isinstance(loc, dict):
                s = ", ".join(filter(None, [(loc.get("city") or "").title(), loc.get("stateCode") or loc.get("state"),
                                            loc.get("countryCode") or loc.get("country")]))
                locs.append(s or loc.get("locationName"))
        pay = None
        pr = [p for p in (d.get("payRange") or []) if p.get("max") not in (None, "0", "0.00")]
        if pr:
            pay = f"${pr[0]['min']} - ${pr[0]['max']} {d.get('payFrequency') or ''}".strip()
        quals = "\n".join(filter(None, [html_to_text(q) for q in (d.get("minimumQualification") or [])]
                                 + [html_to_text(q) for q in (d.get("preferredQualification") or [])]))
        desc = "\n".join(filter(None, [html_to_text(d.get("jobPostingDescription") or d.get("description")), quals]))
        cats = list((d.get("profileMapping") or {}).keys())
        yield raw_posting(
            company, d.get("jobId") or url.rsplit("/", 1)[-1], url, d.get("title"),
            description=desc or None,
            locations=[l for l in locs if l],
            posted_date=(d.get("jobPostingStartDate") or d.get("createdAt") or "")[:10] or None,
            employment_type=", ".join(_v(e) for e in (d.get("employmentTypes") or [])) or None,
            pay_text=pay,
            category=cats[0] if cats else None,
        )
        seen += 1
        if seen >= max_jobs:
            return
