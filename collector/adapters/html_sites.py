"""Server-rendered sites without a public JSON API: Apple, Google, Meta (sitemap), Tesla.

Each lists posting URLs from search pages (or a sitemap), then reads schema.org JobPosting JSON-LD
from the detail page. If a site refuses (robots.txt, 403), BlockedError propagates and the run log
records the company as blocked.
"""
import gzip
import html
import json
import re

import requests
from urllib.parse import urljoin

from ..http import BlockedError
from .common import find_jobposting_jsonld, html_to_text, jobposting_to_raw, raw_posting, seen_before


def _text(r):
    # Pages served without a charset default to ISO-8859-1 in requests; they are UTF-8 in practice.
    if "charset" not in r.headers.get("Content-Type", "").lower():
        r.encoding = "utf-8"
    return r.text


def _detail(company, jid, url, http, fallback_title=None):
    page = _text(http.get(url))
    jp = find_jobposting_jsonld(page)
    if jp:
        return jobposting_to_raw(company, jid, url, jp)
    return raw_posting(company, jid, url, fallback_title, description=html_to_text(page), source_method="html")


def _listing(company, http, max_jobs, page_url, link_re, id_group=1, detail=None):
    seen, page, ids = 0, 1, set()
    while seen < max_jobs:
        html = http.get(page_url(page)).text
        found = [(m.group(id_group), urljoin(page_url(page), m.group(0))) for m in re.finditer(link_re, html)]
        new = list({j: u for j, u in reversed(found) if j not in ids}.items())[::-1]
        if not new:
            break
        for jid, url in new:
            ids.add(jid)
            # The record carries the listed id (Apple's positionId is that same number), or the url maps back to it.
            rec = seen_before(company, http, source_id=jid, url=url)
            if rec:  # already in the history: no detail request
                yield rec
                seen += 1
                if seen >= max_jobs:
                    return
                continue
            yield (detail or _detail)(company, jid, url, http)
            seen += 1
            if seen >= max_jobs:
                return
        page += 1


APPLE_DATA = re.compile(r"window\.__staticRouterHydrationData\s*=\s*JSON\.parse\((\".*?\")\);", re.S)


def _apple_detail(company, jid, url, http):
    # jobs.apple.com has no JSON-LD; the page embeds the full posting as router hydration data.
    m = APPLE_DATA.search(_text(http.get(url)))
    d = json.loads(json.loads(m.group(1)))["loaderData"]["jobDetails"]["jobsData"] if m else None
    if not d:
        return _detail(company, jid, url, http)
    # The earliest per-location posting date; postDateInGMT is refreshed daily on evergreen roles.
    dates = sorted(v.get("postingDate", "") for loc in (d.get("postingPostLocationData") or {}).values()
                   for v in loc.values() if v.get("postingDate"))
    posted = (dates[0] if dates else d.get("postDateInGMT") or "")[:10] or None
    locs = [", ".join(filter(None, [l.get("city"), l.get("stateProvince"), l.get("countryName")])) or l.get("name")
            for l in d.get("locations") or []]
    footers = [it for f in d.get("postingFooters") or [] for it in (f.get("localizations") or {}).get("en_US", [])]
    pay = next((html_to_text(it["content"]) for it in footers if it.get("name") == "Pay & Benefits"), None)
    desc = "\n".join(filter(None, [d.get("jobSummary"), d.get("description"),
                                   "Minimum Qualifications\n" + d["minimumQualifications"] if d.get("minimumQualifications") else None,
                                   "Preferred Qualifications\n" + d["preferredQualifications"] if d.get("preferredQualifications") else None]))
    return raw_posting(company, d.get("positionId") or jid, url, d.get("postingTitle"),
                       description=html_to_text(desc), locations=[l for l in locs if l], posted_date=posted,
                       remote_hint="Remote" if d.get("homeOffice") else None, pay_text=pay,
                       category=", ".join(d.get("teamNames") or []) or None,
                       source_method="html")


def collect_apple(company, params, http, max_jobs, stats):
    loc = params.get("locale", "en-us")
    yield from _listing(company, http, max_jobs,
                        lambda p: f"https://jobs.apple.com/{loc}/search?sort=newest&page={p}",
                        # One role is listed once per store/location (200313970-2015, -0836, ...); keep one per role.
                        rf"/{loc}/details/([0-9]+)(?:-[0-9]+)?/[a-z0-9\-]+", detail=_apple_detail)


def collect_google(company, params, http, max_jobs, stats):
    yield from _listing(company, http, max_jobs,
                        lambda p: f"https://www.google.com/about/careers/applications/jobs/results/?sort_by=date&page={p}",
                        r"jobs/results/(\d{6,})-[a-z0-9\-]+")


JOB_URL = r"/(job|jobs|position|vacanc|requisition|opening|careers?/job)[s]?/|jid-|/details/|jobid=|/job-"


def _sitemap_entries(http, url, depth=0):
    """(loc, lastmod) pairs from a sitemap, following sitemap indexes and gzip."""
    r = http.get(url)
    body = r.content
    if body[:2] == b"\x1f\x8b":
        body = gzip.decompress(body)
    xml = body.decode("utf-8", "replace")
    entries = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>(?:\s*<lastmod>\s*([^<\s]+))?", xml)
    if "<sitemapindex" in xml and depth < 2:
        out = []
        for loc, _ in entries[:60]:
            try:
                out += _sitemap_entries(http, html.unescape(loc), depth + 1)
            except (requests.RequestException, OSError):
                continue
        return out
    return [(html.unescape(l), m) for l, m in entries]


def collect_sitemap(company, params, http, max_jobs, stats):
    """Any career site that lists job pages in its sitemap and marks them up as schema.org JobPosting.
    params: sitemap (one URL) or sitemaps (list); url_pattern (default: common job-page paths)."""
    pattern = params.get("url_pattern", JOB_URL)
    entries = []
    for sm in params.get("sitemaps") or [params["sitemap"]]:
        entries += _sitemap_entries(http, sm)
    entries = {u: m for u, m in entries if re.search(pattern, u, re.I)}
    # Newest first when the sitemap gives lastmod; otherwise keep the site's own order.
    urls = sorted(entries, key=lambda u: entries[u] or "", reverse=True)
    stats["site_total"] = len(urls)
    seen = 0
    for u in urls:
        if "id_pattern" in params:
            m = re.search(params["id_pattern"], u)
        else:  # TalentBrew urls end /<org id>/<job id>; elsewhere the first long number is the id
            m = re.search(r"/\d+/(\d{9,})/?$", u) or re.search(r"(\d{5,})", u)
        jid = m[1] if m else u
        rec = seen_before(company, http, source_id=jid)
        if rec:  # already in the history: no detail request
            yield rec
            seen += 1
            if seen >= max_jobs:
                return
            continue
        try:
            rec = _detail(company, jid, u, http)
        except requests.HTTPError:  # sitemaps lag behind closed postings; skip pages that are gone
            stats["gone"] = stats.get("gone", 0) + 1
            continue
        if rec.get("source_method") != "jsonld":  # not a job page after all
            stats["no_jobposting"] = stats.get("no_jobposting", 0) + 1
            if stats["no_jobposting"] > 20 and not seen:
                return
            continue
        yield rec
        seen += 1
        if seen >= max_jobs:
            return


def collect_tesla(company, params, http, max_jobs, stats):
    # Tesla's listing JSON; normally refused for scripted clients (BlockedError is the expected outcome).
    data = http.get("https://www.tesla.com/cua-api/apps/careers/state").json()
    listings = data.get("listings") or []
    stats["site_total"] = len(listings)
    lookup = data.get("lookup", {})
    for j in listings[:max_jobs]:
        jid = j.get("id")
        url = f"https://www.tesla.com/careers/search/job/{jid}"
        yield raw_posting(company, jid, url, j.get("t"),
                          locations=[(lookup.get("locations") or {}).get(str(j.get("l")), str(j.get("l")))],
                          category=(lookup.get("departments") or {}).get(str(j.get("dp"))),
                          employment_type=(lookup.get("types") or {}).get(str(j.get("y"))))


def collect_refused_by_terms(company, params, http, max_jobs, stats):
    # The site states that automated collection is prohibited without written permission; honor it.
    raise BlockedError(params["reason"])
