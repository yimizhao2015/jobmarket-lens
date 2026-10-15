"""SAP SuccessFactors career sites. Server-rendered search pages where the site has them; newer sites render
search in the browser, so for those the job pages come from the site's sitemap. Detail pages carry
JSON-LD or schema.org microdata."""
import re
from datetime import datetime

from bs4 import BeautifulSoup

from .common import find_jobposting_jsonld, html_to_text, jobposting_to_raw, raw_posting


def collect(company, params, http, max_jobs, stats):
    host = params["host"]
    start, seen = 0, 0
    while seen < max_jobs:
        page = http.get(f"https://{host}/search/",
                        params={"q": "", "sortColumn": "referencedate", "sortDirection": "desc", "startrow": start}).text
        soup = BeautifulSoup(page, "html.parser")
        if start == 0:
            m = re.search(r"Results\s+\d+\s*[–-]\s*\d+\s+of\s+([\d,]+)", soup.get_text(" "))
            stats["site_total"] = int(m.group(1).replace(",", "")) if m else None
        rows = soup.select("tr.data-row") or soup.select("li.job-tile")
        if not rows and start == 0:
            yield from _from_sitemap(company, host, http, max_jobs, stats)
            return
        if not rows:
            break
        for row in rows:
            a = row.select_one("a.jobTitle-link") or row.find("a", href=re.compile(r"/job/"))
            if not a:
                continue
            url = f"https://{host}" + a["href"] if a["href"].startswith("/") else a["href"]
            jid = (re.search(r"/(\d+)/?$", url) or [None, url])[1]
            page = http.get(url).text
            jp = find_jobposting_jsonld(page)
            if jp:
                yield jobposting_to_raw(company, jid, url, jp)
            else:
                # SuccessFactors detail pages carry schema.org microdata rather than JSON-LD.
                dsoup = BeautifulSoup(page, "html.parser")
                desc_el = dsoup.select_one('[itemprop="description"]') or dsoup.select_one(".jobdescription")
                desc = html_to_text(str(desc_el)) if desc_el else None
                date_el = row.select_one(".jobDate")
                try:
                    posted = datetime.strptime(date_el.get_text(strip=True), "%b %d, %Y").date().isoformat()
                except (AttributeError, ValueError):
                    posted = None
                loc_el = row.select_one(".jobLocation")
                yield raw_posting(company, jid, url, a.get_text(strip=True), posted_date=posted, description=desc,
                                  locations=[loc_el.get_text(strip=True)] if loc_el else [], source_method="html")
            seen += 1
            if seen >= max_jobs:
                return
        start += len(rows)


_DATE_LABEL = re.compile(r"(?:Posting Start Date|Date Posted|Posted Date|Posting Date|Date)\s*:?\s*\n?\s*"
                         r"(\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2}|[A-Z][a-z]{2,8}\.? \d{1,2},? \d{4}|\d{1,2}[ -][A-Z][a-z]{2}[ -]\d{4})")
_DATE_FMTS = ("%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d", "%b %d, %Y", "%B %d, %Y", "%b %d %Y", "%d-%b-%Y", "%d %b %Y")


def _parse_date(v):
    if not v:
        return None
    v = v.strip().replace(".", "")
    for f in ("%a %b %d %H:%M:%S %Z %Y",) + _DATE_FMTS:
        try:
            return datetime.strptime(v, f).date().isoformat()
        except ValueError:
            continue
    return v[:10] if re.match(r"\d{4}-\d{2}-\d{2}", v) else None


def _labeled(text, *labels):
    for lab in labels:
        m = re.search(lab + r"\s*:?\s*\n\s*([^\n]{1,80})", text)
        if m and not m.group(1).strip().endswith(":"):
            return m.group(1).strip()
    return None


def _microdata(company, jid, url, page):
    """schema.org microdata; newer SuccessFactors pages only mark up title and description, so date and
    location also come from the page's own labeled fields."""
    soup = BeautifulSoup(page, "html.parser")
    def prop(name):
        el = soup.select_one(f'[itemprop="{name}"]')
        return (el.get("content") or el.get_text(" ", strip=True)) if el else None
    text = soup.get_text("\n", strip=True)
    descs = soup.select('[itemprop="description"]') or soup.select(".jobdescription")
    desc = "\n".join(filter(None, (html_to_text(str(d)) for d in descs)))
    loc = ", ".join(filter(None, [prop("addressLocality"), prop("addressRegion"), prop("addressCountry")]))
    if not loc:
        loc = ", ".join(filter(None, [_labeled(text, "Posting City", "City"), _labeled(text, "State", "Province"),
                                      _labeled(text, "Job Country", "Country")])) or _labeled(text, "Location", "Job Location")
    posted = _parse_date(prop("datePosted"))
    if not posted:
        m = _DATE_LABEL.search(text)
        posted = _parse_date(m.group(1)) if m else None
    title = prop("title") or (soup.title.get_text(strip=True) if soup.title else "")
    title = re.split(r"\s+Job Details\b|\s+\|\s+", title)[0] or None
    return raw_posting(company, jid, url, title,
                       description=desc or None, locations=[loc] if loc else [], posted_date=posted,
                       employment_type=prop("employmentType") or _labeled(text, "Employment Type", "Job Type", "Shift Type"),
                       source_method="html")


def _from_sitemap(company, host, http, max_jobs, stats):
    from .html_sites import _sitemap_entries, _text
    import requests
    entries = {u: m for u, m in _sitemap_entries(http, f"https://{host}/sitemap.xml") if "/job/" in u}
    urls = sorted(entries, key=lambda u: entries[u] or "", reverse=True)
    stats["site_total"] = len(urls)
    stats["method"] = "sitemap"
    seen = 0
    for url in urls:
        jid = (re.search(r"/(\d+)/?$", url) or [None, url])[1]
        try:
            page = _text(http.get(url))
        except requests.HTTPError:
            stats["gone"] = stats.get("gone", 0) + 1
            continue
        jp = find_jobposting_jsonld(page)
        yield jobposting_to_raw(company, jid, url, jp) if jp else _microdata(company, jid, url, page)
        seen += 1
        if seen >= max_jobs:
            return
