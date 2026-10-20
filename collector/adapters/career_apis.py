"""Career sites whose job list is drawn in the browser but comes from a JSON service (or a paged HTML search)
that also answers plain HTTP requests, so no browser is needed:

directemployers  DirectEmployers ".jobs" sites (News Corp, Southern Company): the site's own search service,
                 prod-search-api.jobsyn.org, keyed by the site's host name (x-origin). Each hit carries the full text.
mcloud           Symphony Talent CWS sites (Edison): the jobs API the site's script calls
                 (jobsapi-google.m-cloud.io), keyed by the site's company name. Each hit carries the full text.
coveo            Coveo-indexed job listings (SLB): the site's Coveo search, with the public search key the listing
                 page itself carries (read at run time, never stored). Each hit carries the full text.
fastenal         jobs.fastenal.com: the DataTables feed (/load-jobs, session CSRF token) behind the job list; job
                 pages give the text.
eog              careers.eogresources.com: the ASP search page lists every opening with its posted date; job pages
                 give the text.
pca              careers.packagingcorp.com: the search page lists ten openings per page (?spage=N) with posted
                 dates; job pages give the text.
"""
import json
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .common import find_jobposting_jsonld, html_to_text, jobposting_to_raw, raw_posting, seen_before
from .html_sites import _text


def _ms_date(ms):
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError):
        return None


def _mdy(v):
    """'9/23/2026' or '10/19/26' as YYYY-MM-DD."""
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", v or "")
    if not m:
        return None
    y = int(m.group(3))
    y = y + 2000 if y < 100 else y
    return f"{y}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"


def _clean(text):
    if not text:
        return None
    text = re.sub(r"[ \t\xa0]+", " ", text)
    return re.sub(r"\s*\n\s*(\n\s*)*", "\n", text).strip() or None


def _capped(gen, max_jobs):
    for n, rec in enumerate(gen, 1):
        yield rec
        if n >= max_jobs:
            return


# --- DirectEmployers ---------------------------------------------------------------------------------------------

DE_API = "https://prod-search-api.jobsyn.org/api/v1/solr/search"


def _directemployers(company, params, http, stats):
    host = params["host"]
    page = 1
    while True:
        data = http.get(DE_API, params={"page": page, "num_items": 15},
                        headers={"x-origin": host, "Accept": "application/json"}).json()
        pag = data.get("pagination") or {}
        if page == 1:
            stats["site_total"] = pag.get("total")
        jobs = data.get("jobs") or []
        for j in jobs:
            loc = j.get("location_exact") or ""
            slug = re.sub(r"[^a-z0-9]+", "-", loc.lower()).strip("-") or "none"
            url = f"https://{host}/{slug}/{j.get('title_slug') or 'job'}/{j['guid']}/job/"
            yield raw_posting(company, j["guid"], url, j.get("title_exact"),
                              description=_clean(j.get("description")),
                              locations=[loc] if loc else [],
                              posted_date=(j.get("date_new") or j.get("date_added") or "")[:10] or None,
                              category=j.get("company_exact"),  # the News Corp business / Southern Co. unit
                              )
        if not jobs or not pag.get("has_more_pages"):
            return
        page += 1


def collect_directemployers(company, params, http, max_jobs, stats):
    """params: host (the .jobs site's host name). Hits come newest first."""
    yield from _capped(_directemployers(company, params, http, stats), max_jobs)


# --- Symphony Talent (m-cloud) -----------------------------------------------------------------------------------

MCLOUD_API = "https://jobsapi-google.m-cloud.io/api/job/search"


def _mcloud(company, params, http, stats):
    offset = 0
    while True:
        data = http.get(MCLOUD_API, params={"pageSize": 100, "offset": offset, "companyName": params["company_name"],
                                            "orderBy": "posting_publish_time desc"}).json()
        if offset == 0:
            stats["site_total"] = data.get("totalHits")
        hits = data.get("searchResults") or []
        for h in hits:
            j = h.get("job") or {}
            locs = [", ".join(filter(None, [j.get("primary_city"), j.get("primary_state"), j.get("primary_country")]))]
            for a in j.get("addtnl_locations") or []:
                if isinstance(a, dict):
                    locs.append(", ".join(filter(None, [a.get("city"), a.get("state"), a.get("country")])))
            yield raw_posting(company, j["id"], j.get("url"), j.get("title"),
                              description=html_to_text(j.get("description")),
                              locations=[l for l in dict.fromkeys(locs) if l],
                              posted_date=(j.get("open_date") or "")[:10] or None,
                              employment_type=j.get("employment_type") or j.get("job_type"),
                              remote_hint=j.get("location_type"),
                              pay_text=j.get("salary"),
                              category=j.get("primary_category"),
                              level_hint=j.get("level"))
        offset += len(hits)
        if not hits or offset >= (data.get("totalHits") or 0):
            return


def collect_mcloud(company, params, http, max_jobs, stats):
    """params: company_name (the site's "companies/<uuid>" value from its cws_opts). Newest first."""
    yield from _capped(_mcloud(company, params, http, stats), max_jobs)


# --- Coveo ---------------------------------------------------------------------------------------------------------

def _coveo(company, params, http, stats):
    page = _text(http.get(params["listing"]))
    m = re.search(r'accessToken"\s+value="([^"]+)"', page)
    if not m:
        raise RuntimeError("no Coveo search key on the listing page")
    key, org = m.group(1), params["organization"]
    api = f"https://{org}.org.coveo.com/rest/search/v2"
    first = 0
    while True:
        body = {"q": "", "cq": params["cq"], "pipeline": params.get("pipeline"), "searchHub": params.get("search_hub"),
                "numberOfResults": 100, "firstResult": first, "sortCriteria": "@jobposteddate descending"}
        data = http.post(api, params={"organizationId": org}, json=body,
                         headers={"Authorization": f"Bearer {key}"}).json()
        if first == 0:
            stats["site_total"] = data.get("totalCount")
        res = data.get("results") or []
        for r in res:
            raw = r.get("raw") or {}
            url = re.sub(r"\s+\d+$", "", (r.get("clickUri") or "").strip())
            jid = (re.search(r"[?&]id=([^&\s]+)", url) or [None, raw.get("permanentid")])[1]
            countries = raw.get("country") or []
            countries = countries if isinstance(countries, list) else [countries]
            desc = re.sub(r"^\s*<!\[CDATA\[|\]\]>\s*$", "", raw.get("description") or "")
            cat = raw.get("category")
            yield raw_posting(company, jid, url, raw.get("title") or r.get("title"),
                              description=html_to_text(desc),
                              locations=[", ".join(filter(None, [raw.get("city"), c])) for c in countries] or
                                        ([raw["city"]] if raw.get("city") else []),
                              posted_date=_ms_date(raw.get("jobposteddate")),
                              category=", ".join(cat) if isinstance(cat, list) else cat,
                              level_hint=", ".join(raw.get("jobexperiencelevel") or []) or None)
        first += len(res)
        if not res or first >= (data.get("totalCount") or 0):
            return


def collect_coveo(company, params, http, max_jobs, stats):
    """params: listing (job-listing page carrying the public search key), organization, cq, pipeline, search_hub."""
    yield from _capped(_coveo(company, params, http, stats), max_jobs)


# --- Fastenal --------------------------------------------------------------------------------------------------------

def collect_fastenal(company, params, http, max_jobs, stats):
    host = params.get("host", "jobs.fastenal.com")
    page = _text(http.get(f"https://{host}/jobs"))
    token = re.search(r'name="_csrf" content="([^"]+)"', page).group(1)
    rows, start = [], 0
    while True:
        data = http.post(f"https://{host}/load-jobs",
                         data={"draw": 1, "start": start, "length": 100, "search[value]": "", "sortColumn": 0,
                               "sortDir": "asc", "query": ""},
                         headers={"X-CSRF-TOKEN": token, "X-Requested-With": "XMLHttpRequest"}).json()
        got = data.get("data") or []
        rows += got
        start += len(got)
        if not got or start >= (data.get("recordsTotal") or 0):
            break
    stats["site_total"] = len(rows)
    rows.sort(key=lambda r: r.get("approvedDate") or 0, reverse=True)  # newest first
    seen = 0
    for r in rows:
        jid = str(r["jobId"])
        url = f"https://{host}/details/{jid}"
        rec = seen_before(company, http, source_id=jid)
        if not rec:
            try:
                soup = BeautifulSoup(_text(http.get(url)), "html.parser")
            except requests.HTTPError:
                stats["gone"] = stats.get("gone", 0) + 1
                continue
            desc = soup.select_one(".cms-job-description")
            loc = ", ".join(filter(None, [r.get("city"), r.get("state")]))
            rec = raw_posting(company, jid, url, r.get("title"),
                              description=html_to_text(str(desc).replace("\r", "")) if desc else None,
                              locations=[loc] if loc else [],
                              posted_date=_ms_date(r.get("approvedDate")),
                              employment_type=r.get("type"),
                              category=r.get("department"),
                              source_method="html")
        yield rec
        seen += 1
        if seen >= max_jobs:
            return


# --- EOG Resources ---------------------------------------------------------------------------------------------------

def _loose_jobposting(page):
    """EOG's JSON-LD has a stray closing brace after the object; read the object and ignore the rest."""
    jp = find_jobposting_jsonld(page)
    if jp:
        return jp
    for m in re.finditer(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', page, re.S):
        try:
            obj, _ = json.JSONDecoder().raw_decode(m.group(1).strip())
        except ValueError:
            continue
        if isinstance(obj, dict) and obj.get("@type") == "JobPosting":
            return obj
    return None


def collect_eog(company, params, http, max_jobs, stats):
    base = params.get("listing", "https://careers.eogresources.com/process_jobsearch.asp")
    soup = BeautifulSoup(_text(http.get(base)), "html.parser")
    rows = []
    for item in soup.select(".list-group-item"):
        a = item.find("a", href=re.compile(r"jo_num=\d+"))
        if not a:
            continue
        jid = re.search(r"jo_num=(\d+)", a["href"]).group(1)
        rows.append((jid, urljoin(base, f"jobdetails.asp?jo_num={jid}"),
                     _mdy((re.search(r"Posted\s*:?\s*([\d/]+)", item.get_text(" ")) or [None, None])[1])))
    rows = list({r[0]: r for r in rows}.values())
    stats["site_total"] = len(rows)
    rows.sort(key=lambda r: r[2] or "", reverse=True)
    seen = 0
    for jid, url, posted in rows:
        rec = seen_before(company, http, source_id=jid)
        if not rec:
            page = _text(http.get(url))
            jp = _loose_jobposting(page)
            if jp:
                rec = jobposting_to_raw(company, jid, url, jp)
            else:
                rec = raw_posting(company, jid, url, None, description=html_to_text(page), source_method="html")
            # The posted date the site shows on the list and the job page ("Posted 9/23/2026"); its JSON-LD
            # carries a different, unpadded date.
            m = re.search(r"Posted:?\s*(\d{1,2}/\d{1,2}/\d{4})", BeautifulSoup(page, "html.parser").get_text(" "))
            rec["posted_date"] = _mdy(m.group(1)) if m else posted
        yield rec
        seen += 1
        if seen >= max_jobs:
            return


# --- Packaging Corporation of America ------------------------------------------------------------------------------

def collect_pca(company, params, http, max_jobs, stats):
    base = params.get("listing", "https://careers.packagingcorp.com/career-search/")
    seen, page, ids = 0, 1, set()
    while seen < max_jobs:
        soup = BeautifulSoup(_text(http.get(base, params={"spage": page})), "html.parser")
        if page == 1:
            m = re.search(r"of\s+([\d,]+)", (soup.select_one(".holder--count") or soup).get_text(" "))
            stats["site_total"] = int(m.group(1).replace(",", "")) if m else None
        rows = [tr for tr in soup.select("#postings tr") if tr.select_one("td.id")]
        new = [tr for tr in rows if tr.select_one("td.id").get_text(strip=True) not in ids]
        if not new:
            return
        for tr in new:
            jid = tr.select_one("td.id").get_text(strip=True)
            ids.add(jid)
            a = tr.select_one("td.apply a[href]")
            url = a["href"] if a else None
            rec = seen_before(company, http, source_id=jid, url=url)
            if not rec:
                if not url:
                    continue
                try:
                    dpage = _text(http.get(url))
                except requests.HTTPError:
                    stats["gone"] = stats.get("gone", 0) + 1
                    continue
                dsoup = BeautifulSoup(dpage, "html.parser")
                desc = dsoup.select_one(".job-description")
                jp = find_jobposting_jsonld(dpage) or {}
                pay = re.search(r"Salary:\s*([^\n]+?)(?:\s{2,}|\n|$)", dsoup.get_text("\n"))
                loc = tr.select_one("td.location").get_text(" ", strip=True)
                rec = raw_posting(company, jid, url, tr.select_one("td.title").get_text(" ", strip=True),
                                  description=html_to_text(str(desc)) if desc else html_to_text(jp.get("description")),
                                  locations=[loc] if loc else [],
                                  # the date the list and the job page show; the JSON-LD date differs from it
                                  posted_date=_mdy(tr.select_one("td.posted").get_text(strip=True)),
                                  employment_type=jp.get("employmentType"),
                                  pay_text=pay.group(1).strip() if pay else None,
                                  source_method="html")
            yield rec
            seen += 1
            if seen >= max_jobs:
                return
        page += 1
