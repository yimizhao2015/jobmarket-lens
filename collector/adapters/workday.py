"""Workday CXS JSON API (used by NVIDIA, Broadcom, Lilly, Micron, Walmart, J&J, Mastercard, Intel, AbbVie).

List:   POST https://{host}/wday/cxs/{tenant}/{site}/jobs   {"limit":20,"offset":N,"searchText":"","appliedFacets":{}}
Detail: GET  https://{host}/wday/cxs/{tenant}/{site}{externalPath}
"""
from .common import html_to_text, raw_posting


def collect(company, params, http, max_jobs, stats):
    host, tenant, site = params["host"], params["tenant"], params["site"]
    base = f"https://{host}/wday/cxs/{tenant}/{site}"
    public = f"https://{host}/{site}"
    offset, seen = 0, 0
    while seen < max_jobs:
        r = http.post(base + "/jobs", json={"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": ""})
        data = r.json()
        if offset == 0:
            stats["site_total"] = data.get("total")
        posts = data.get("jobPostings") or []
        if not posts:
            break
        for p in posts:
            path = p.get("externalPath")
            if not path:
                continue
            try:
                d = http.get(base + path).json().get("jobPostingInfo", {})
            except Exception as e:  # keep the list-level record rather than drop the posting
                stats.setdefault("detail_errors", 0)
                stats["detail_errors"] += 1
                d = {}
            locs = [d.get("location") or p.get("locationsText")] + list(d.get("additionalLocations") or [])
            yield raw_posting(
                company, d.get("jobReqId") or (p.get("bulletFields") or [path])[0], public + path,
                d.get("title") or p.get("title"),
                description=html_to_text(d.get("jobDescription")),
                locations=[l for l in locs if l],
                posted_date=(d.get("startDate") or "")[:10] or None,
                employment_type=d.get("timeType"),
                remote_hint=d.get("remoteType"),
            )
            seen += 1
            if seen >= max_jobs:
                return
        offset += len(posts)
