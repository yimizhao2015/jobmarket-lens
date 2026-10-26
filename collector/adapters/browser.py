"""Career sites whose job list exists only in a real browser (headless Chromium through Playwright).

One browser per company run, closed as soon as the list has been read; job pages that serve their text without
a browser are then read with the ordinary polite HTTP client. robots.txt is checked for every page the browser
opens, and a page answered with 401/403 or a challenge stops the run as blocked (BlockedError).

params.kind selects the site type:

taleo_legacy  Legacy Oracle Taleo career sections (Weyerhaeuser, Evergy) that have no JSON search service and page
              their job list through browser-side session state. The browser opens jobsearch.ftl and steps through
              the list's pages, reading each row (title, location, posted date, job number) from the rendered table;
              job pages (jobdetail.ftl) are then read over HTTP like the taleo adapter.
              params: host, section.
adp           ADP Recruiting career sites (myjobs.adp.com, Sempra): the site loads its openings from my.adp.com with a
              session token minted in the browser. The browser opens each career site, captures the site's own job
              request, and replays it with a larger page size inside the same browser session. Each opening carries
              its full text; its posting date comes from the opening's own search-meta record (one request each,
              skipped for openings already in the history). params: sites (career-site names, e.g. "sdgecareers").
listing_links The company's own job list, drawn by the browser page by page (Wynn): the browser reads each listing
              page's job links until a page adds none; each job page is then read over HTTP. params: listing (URL
              with {page}), link_pattern (regex, group 1 = job id), detail_url (job page URL with {id}; default the
              matched link), detail ("smartrecruiters" for jobs.smartrecruiters.com pages, else JSON-LD).
"""
import os
import re
from contextlib import contextmanager
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests

from ..http import BlockedError
from . import smartrecruiters
from .common import html_to_text, raw_posting, seen_before
from .html_sites import _detail
from .taleo import _date, _history

SANDBOX_CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
CHALLENGE = re.compile(r"captcha|client challenge|access denied|are you a robot|verify you are human", re.I)


@contextmanager
def _page(http):
    from playwright.sync_api import sync_playwright  # imported here so other adapters run without playwright

    kw = {"headless": True}
    if os.path.exists(SANDBOX_CHROME):  # this sandbox; CI uses the browser `playwright install` put in place
        kw["executable_path"] = SANDBOX_CHROME
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if proxy:
        kw["proxy"] = {"server": proxy}
    with sync_playwright() as p:
        browser = p.chromium.launch(**kw)
        try:
            ua = p.devices["Desktop Chrome"]["user_agent"] + " " + http.s.headers["User-Agent"]
            ctx = browser.new_context(user_agent=ua, locale="en-US")
            ctx.set_default_timeout(45000)
            yield ctx.new_page()
        finally:
            browser.close()


def _open(page, http, url):
    if not http._allowed(url):
        raise BlockedError(f"robots.txt disallows {url}")
    resp = page.goto(url, wait_until="domcontentloaded")
    if resp is not None and resp.status in (401, 403):
        raise BlockedError(f"HTTP {resp.status} from {url}")
    try:
        page.wait_for_load_state("networkidle", timeout=20000)
    except Exception:  # pages that keep polling never go idle; the content is there anyway
        pass
    if CHALLENGE.search(page.title() or ""):
        raise BlockedError(f"bot challenge at {url}")
    return resp


# --- legacy Taleo ------------------------------------------------------------------------------------------------

_ROWS_JS = """() => Array.from(document.querySelectorAll('[id^="requisitionListInterface.reqTitleLinkAction.row"]')).map(a => {
  const n = a.id.replace(/^.*\\.row/, '');
  const v = k => { const e = document.getElementById('requisitionListInterface.' + k + '.row' + n); return e ? e.innerText.trim() : null; };
  return {title: a.innerText.trim(), location: v('reqBasicLocation'), posted: v('reqPostingDate'),
          number: v('reqContestNumberValue')};
})"""


def _taleo_list(page, http, host, section, stats):
    _open(page, http, f"https://{host}/careersection/{section}/jobsearch.ftl?lang=en")
    # The list, or the site's own "no jobs" message (an empty section is reported as empty, not as an error)
    page.wait_for_function(
        "() => document.querySelector('[id^=\"requisitionListInterface.reqTitleLinkAction.row\"]') ||"
        " /no jobs (are )?(currently )?(available|match)/i.test(document.body.innerText)")
    if not page.locator('[id^="requisitionListInterface.reqTitleLinkAction.row"]').count():
        stats["site_total"] = 0
        return []
    m = re.search(r"([\d,]+)\s+jobs? found", page.inner_text("body"))
    stats["site_total"] = int(m.group(1).replace(",", "")) if m else None
    rows = {}
    for _ in range(200):  # pages; a safety bound far above any section's size
        got = page.evaluate(_ROWS_JS)
        new = [r for r in got if r["number"] and r["number"] not in rows]
        if not new:
            break
        rows.update((r["number"], r) for r in new)
        nxt = page.locator('a[id$=".Next"]:visible').first
        if not nxt.count() or nxt.get_attribute("aria-disabled") == "true":
            break
        first = got[0]["number"]
        page.wait_for_timeout(int(http.delay * 1000))
        nxt.click()
        try:
            page.wait_for_function(
                "n => { const e = document.getElementById('requisitionListInterface.reqContestNumberValue.row1');"
                " return e && e.innerText.trim() !== n; }", arg=first, timeout=30000)
        except Exception:
            break
    return list(rows.values())


def _collect_taleo_legacy(company, params, http, max_jobs, stats):
    host, section = params["host"], params["section"]
    with _page(http) as page:
        rows = _taleo_list(page, http, host, section, stats)
    stats["listed"] = len(rows)
    for r in rows:
        r["_date"] = _date(r.get("posted"))
    rows.sort(key=lambda r: r["_date"] or "", reverse=True)
    seen = 0
    for r in rows:
        url = f"https://{host}/careersection/{section}/jobdetail.ftl?job={r['number']}&lang=en"
        rec = seen_before(company, http, source_id=r["number"])
        if not rec:
            parts = _history(http.get(url).text)
            rich = list(dict.fromkeys(p[3:] for p in parts if p.startswith("!*!")))  # each rich field appears twice
            rec = raw_posting(company, r["number"], url, r["title"],
                              description=html_to_text("\n".join(rich)) or None,
                              # several locations come comma-separated, each written Country-State-City
                              locations=[l.strip() for l in (r.get("location") or "").split(",") if l.strip()],
                              posted_date=r["_date"],
                              source_method="html")
        yield rec
        seen += 1
        if seen >= max_jobs:
            return


# --- ADP Recruiting --------------------------------------------------------------------------------------------------

def _with(url, **params):
    p = urlparse(url)
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k not in params]
    q += [(k, str(v)) for k, v in params.items()]
    return urlunparse(p._replace(query=urlencode(q, safe="$,() ")))


def _adp_site(company, page, http, site):
    captured = {}

    def on_request(req):
        if "job-requisitions/apply-custom-filters" in req.url and "req" not in captured:
            captured["req"] = (req.url, req.headers)

    page.on("request", on_request)
    try:
        _open(page, http, f"https://myjobs.adp.com/{site}/cx")
        page.wait_for_timeout(2000)
    finally:
        page.remove_listener("request", on_request)
    if "req" not in captured:
        raise RuntimeError(f"ADP site {site} made no job request")
    url, headers = captured["req"]
    headers = {k: v for k, v in headers.items() if k.lower() in ("myjobstoken", "rolecode", "accept", "accept-language")}
    reqs, skip, total = [], 0, None
    while True:
        r = page.request.get(_with(url, **{"$top": 100, "$skip": skip}), headers=headers)
        if r.status in (401, 403):
            raise BlockedError(f"HTTP {r.status} from ADP job list ({site})")
        data = r.json()
        total = data.get("count") if total is None else total
        got = data.get("jobRequisitions") or []
        reqs += got
        skip += len(got)
        if not got or skip >= (total or 0):
            break
        page.wait_for_timeout(int(http.delay * 1000))
    # The list carries no date; each opening's search-meta record gives the time it was posted to the site
    # (postingInstructions[].timestampLastPosted, the only posting date ADP exposes; postDate stays empty).
    meta = re.sub(r"/job-requisitions/apply-custom-filters\?.*$", "/job-requisitions/search-meta/", url)
    for j in reqs:
        if seen_before(company, http, source_id=j.get("clientRequisitionID") or j["reqId"]):
            j["_seen"] = True
            continue
        page.wait_for_timeout(int(http.delay * 1000))
        r = page.request.get(meta + j["reqId"], headers=headers)
        if r.ok:
            full = (r.json().get("jobRequisitions") or [{}])[0]
            posted = sorted(p.get("timestampLastPosted") or "" for p in full.get("postingInstructions") or []
                            if (p.get("postingChannel") or {}).get("typeCode", {}).get("longName", "External") == "External")
            j["postingDate"] = next((d for d in posted if d), None)
    return reqs, total or 0


def _name(v):
    return v.get("longName") or v.get("codeValue") if isinstance(v, dict) else v


def _adp_rec(company, site, j):
    locs = []
    for loc in j.get("requisitionLocations") or []:
        a = loc.get("address") or {}
        locs.append(", ".join(filter(None, [a.get("cityName"), (a.get("countrySubdivisionLevel1") or {}).get("codeValue"),
                                            (a.get("country") or {}).get("codeValue")])))
    desc = "\n".join(filter(None, [j.get("jobDescription"), j.get("jobQualifications")]))
    rid = j.get("clientRequisitionID") or j["reqId"]
    return raw_posting(company, rid, f"https://myjobs.adp.com/{site}/cx/job-details?reqId={j['reqId']}",
                       j.get("publishedJobTitle") or j.get("jobTitle"),
                       description=html_to_text(desc),
                       locations=[l for l in dict.fromkeys(locs) if l],
                       posted_date=(j.get("postingDate") or "")[:10] or None,
                       employment_type=_name(j.get("workLevelCode")),  # "Full-time" on these sites
                       category=site)


def _collect_adp(company, params, http, max_jobs, stats):
    recs, total = [], 0
    with _page(http) as page:
        for site in params["sites"]:
            reqs, n = _adp_site(company, page, http, site)
            total += n
            recs += [seen_before(company, http, source_id=j.get("clientRequisitionID") or j["reqId"],
                                 url=f"https://myjobs.adp.com/{site}/cx/job-details?reqId={j['reqId']}")
                     if j.get("_seen") else _adp_rec(company, site, j) for j in reqs]
    stats["site_total"] = total
    recs = list({r["source_id"]: r for r in recs}.values())
    recs.sort(key=lambda r: r.get("posted_date") or "", reverse=True)
    yield from recs[:max_jobs]


# --- rendered listing links -------------------------------------------------------------------------------------

def _collect_listing_links(company, params, http, max_jobs, stats):
    link_re = re.compile(params["link_pattern"])
    found = {}
    with _page(http) as page:
        for n in range(1, 500):
            _open(page, http, params["listing"].format(page=n))
            try:
                page.wait_for_function(f"() => Array.from(document.links).some(a => new RegExp({params['link_pattern']!r}).test(a.href))",
                                       timeout=15000)
            except Exception:
                pass
            links = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
            new = {m.group(1): m.group(0) for m in map(link_re.search, links) if m and m.group(1) not in found}
            if not new:
                break
            found.update(new)
            if len(found) >= max_jobs:
                break
            page.wait_for_timeout(int(http.delay * 1000))
    stats["listed"] = len(found)
    seen = 0
    for jid, link in found.items():  # the site's own order (listing sorted newest first)
        url = params["detail_url"].format(id=jid) if params.get("detail_url") else link
        rec = seen_before(company, http, source_id=jid, url=url)
        if not rec:
            try:
                if params.get("detail") == "smartrecruiters":
                    rec = smartrecruiters.site_detail(company, jid, url, http)
                else:
                    rec = _detail(company, jid, url, http)
            except requests.HTTPError:
                stats["gone"] = stats.get("gone", 0) + 1
                continue
        yield rec
        seen += 1
        if seen >= max_jobs:
            return


KINDS = {"taleo_legacy": _collect_taleo_legacy, "adp": _collect_adp, "listing_links": _collect_listing_links}


def collect(company, params, http, max_jobs, stats):
    yield from KINDS[params["kind"]](company, params, http, max_jobs, stats)
