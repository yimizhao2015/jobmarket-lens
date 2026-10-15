"""Jibe (iCIMS) career sites (AMD): GET https://{host}/api/jobs?page=N&limit=100&sortBy=posted_date"""
from .common import html_to_text, raw_posting


def collect(company, params, http, max_jobs, stats):
    host = params["host"]
    page, seen = 1, 0
    while seen < max_jobs:
        data = http.get(f"https://{host}/api/jobs",
                        params={"page": page, "limit": 100, "sortBy": "posted_date", "descending": "true"}).json()
        if page == 1:
            stats["site_total"] = data.get("totalCount") or data.get("count")
        jobs = data.get("jobs") or []
        if not jobs:
            break
        for item in jobs:
            j = item.get("data", item)
            locs = [l.get("location_name") or l.get("location") for l in (j.get("all_locations") or j.get("locations") or [])
                    if isinstance(l, dict)] or [j.get("full_location") or j.get("location_name")]
            yield raw_posting(
                company, j.get("req_id") or j.get("slug"), j.get("apply_url") or f"https://{host}/careers-home/jobs/{j.get('slug')}",
                j.get("title"),
                description=html_to_text("\n".join(filter(None, [j.get("description"), j.get("qualifications"), j.get("responsibilities")]))),
                locations=[l for l in locs if l],
                posted_date=(j.get("posted_date") or j.get("create_date") or "")[:10] or None,
                employment_type=j.get("employment_type"),
                remote_hint=j.get("location_type") or j.get("tags1"),
                category=", ".join(j.get("categories", [{}])[0].values()) if j.get("categories") else None,
            )
            seen += 1
            if seen >= max_jobs:
                return
        page += 1
