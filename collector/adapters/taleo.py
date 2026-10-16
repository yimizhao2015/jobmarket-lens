"""Oracle Taleo Enterprise career sections (Valero, D.R. Horton, Textron).

List:   POST https://{host}/careersection/rest/jobboard/searchjobs?lang=en&portal={portal}  (the section's own
        JSON search; portal is read from its jobsearch.ftl page)
Detail: GET  https://{host}/careersection/{section}/jobdetail.ftl?job={contestNo}  (the posting's fields travel in
        the page's "initialHistory" value, '!|!'-separated; rich-text fields start with '!*!')
"""
import html
import json
import re
from datetime import datetime
from urllib.parse import unquote

from .common import html_to_text, raw_posting

_DATE = re.compile(r"^([A-Z][a-z]{2}\.? \d{1,2}, \d{4}|\d{1,2}/\d{1,2}/\d{4})")


def _date(v):
    m = _DATE.match((v or "").strip())
    if not m:
        return None
    for f in ("%b %d, %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(m.group(1).replace(".", ""), f).date().isoformat()
        except ValueError:
            continue
    return None


def _history(page):
    m = re.search(r'id="initialHistory"[^>]*value="([^"]*)"', page) or re.search(r'value="([^"]*)"[^>]*id="initialHistory"', page)
    return [unquote(html.unescape(p)).replace("\\:", ":") for p in (m.group(1) if m else "").split("!|!")]


def collect(company, params, http, max_jobs, stats):
    host, section = params["host"], params["section"]
    page = http.get(f"https://{host}/careersection/{section}/jobsearch.ftl", params={"lang": "en"}).text
    portal = re.search(r"portalNo:\s*'(\d+)'", page).group(1)
    body = {"multilineEnabled": False, "sortingSelection": {"sortBySelectionParam": "3", "ascendingSortingOrder": "false"},
            "fieldData": {"fields": {"KEYWORD": "", "LOCATION": ""}, "valid": True},
            "filterSelectionParam": {"searchFilterSelections": []},
            "advancedSearchFiltersSelectionParam": {"searchFilterSelections": []}}
    reqs, page_no = [], 1
    while True:
        data = http.post(f"https://{host}/careersection/rest/jobboard/searchjobs", params={"lang": "en", "portal": portal},
                         json=dict(body, pageNo=page_no), headers={"tz": "GMT-05:00"}).json()
        got = data.get("requisitionList") or []
        reqs += got
        total = (data.get("pagingData") or {}).get("totalCount") or 0
        if not got or len(reqs) >= total or len(reqs) >= max_jobs * 2:
            break
        page_no += 1
    stats["site_total"] = total
    for q in reqs:
        cols = q.get("column") or []
        q["_date"] = next((d for d in map(_date, cols) if d), None)
    # Newest first when the list shows dates; otherwise keep the section's own order.
    reqs.sort(key=lambda q: q["_date"] or "", reverse=True)
    for q in reqs[:max_jobs]:
        cols = q.get("column") or []
        url = f"https://{host}/careersection/{section}/jobdetail.ftl?job={q['contestNo']}&lang=en"
        parts = _history(http.get(url).text)
        rich = list(dict.fromkeys(p[3:] for p in parts if p.startswith("!*!")))  # each rich field appears twice
        locs = []
        for i in q.get("locationsColumns") or []:
            try:
                locs += json.loads(cols[i])
            except (IndexError, ValueError):
                pass
        yield raw_posting(
            company, q["contestNo"], url, cols[q.get("linkedColumn") or 0].strip() if cols else None,
            description=html_to_text("\n".join(rich)) or None,
            locations=locs,
            posted_date=q["_date"] or next((d for d in map(_date, parts) if d), None),
            source_method="html",
        )


def collect_business_edition(company, params, http, max_jobs, stats):
    """Taleo Business Edition (NVR): the career website's RSS feed lists every open requisition with its full text.
    GET https://{host}/{dc}/ats/servlet/Rss?org={org}&cws={cws}"""
    from email.utils import parsedate_to_datetime
    host, dc, org, cws = params["host"], params["dc"], params["org"], params["cws"]
    feed = http.get(f"https://{host}/{dc}/ats/servlet/Rss", params={"org": org, "cws": cws}).text
    items = re.findall(r"<item>(.*?)</item>", feed, re.S)
    stats["site_total"] = len(items)

    def tag(it, name):
        m = re.search(rf"<{name}>(.*?)</{name}>", it, re.S)
        return html.unescape(m.group(1).strip()) if m else None

    recs = []
    for it in items:
        try:
            posted = parsedate_to_datetime(tag(it, "pubDate")).date().isoformat()
        except (TypeError, ValueError):
            posted = None
        rid = tag(it, "taleo:reqId")
        recs.append(raw_posting(
            company, rid, tag(it, "link") or f"https://{host}/{dc}/ats/careers/requisition.jsp?org={org}&cws={cws}&rid={rid}",
            tag(it, "title"),
            description=html_to_text(tag(it, "taleo:html-description")) or tag(it, "description"),
            locations=[l for l in [tag(it, "taleo:location")] if l],
            posted_date=posted,
            category=tag(it, "taleo:department"),
            source_method="html",
        ))
    recs.sort(key=lambda r: r["posted_date"] or "", reverse=True)
    yield from recs[:max_jobs]
