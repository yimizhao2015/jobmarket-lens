"""SAP SuccessFactors career site (ExxonMobil). Server-rendered search pages, JSON-LD on detail pages."""
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
