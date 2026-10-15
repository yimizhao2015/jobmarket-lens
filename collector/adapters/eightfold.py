"""Eightfold career sites (Microsoft). Tries the v2 apply API, then the newer PCSX API."""
from datetime import datetime, timezone

from .common import html_to_text, raw_posting


def _iso(ts):
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError):
        return None


def _v2(company, host, domain, http, max_jobs, stats):
    start, seen = 0, 0
    while seen < max_jobs:
        data = http.get(f"https://{host}/api/apply/v2/jobs",
                        params={"domain": domain, "start": start, "num": 10, "sort_by": "timestamp"}).json()
        if start == 0:
            stats["site_total"] = data.get("count")
        pos = data.get("positions") or []
        if not pos:
            break
        for p in pos:
            d = http.get(f"https://{host}/api/apply/v2/jobs/{p['id']}", params={"domain": domain}).json()
            yield raw_posting(
                company, p.get("display_job_id") or p["id"], p.get("canonicalPositionUrl") or f"https://{host}/careers/job/{p['id']}",
                p.get("name"),
                description=html_to_text(d.get("job_description")),
                locations=p.get("locations") or [p.get("location")],
                posted_date=_iso(p.get("t_create")),
                employment_type=d.get("type"),
                remote_hint=p.get("work_location_option"),
                category=p.get("department"),
            )
            seen += 1
            if seen >= max_jobs:
                return
        start += len(pos)


def _pcsx(company, host, domain, http, max_jobs, stats):
    start, seen = 0, 0
    while seen < max_jobs:
        data = http.get(f"https://{host}/api/pcsx/search",
                        params={"domain": domain, "start": start, "num": 10, "sort_by": "timestamp", "query": ""}).json()
        data = data.get("data", data)
        if start == 0:
            stats["site_total"] = data.get("count")
        pos = data.get("positions") or []
        if not pos:
            break
        for p in pos:
            d = http.get(f"https://{host}/api/pcsx/position_details",
                         params={"position_id": p["id"], "domain": domain}).json()
            d = d.get("data", d)
            yield raw_posting(
                company, p.get("displayJobId") or p["id"], f"https://{host}/careers/job/{p['id']}",
                p.get("name"),
                description=html_to_text(d.get("jobDescription")),
                locations=p.get("standardizedLocations") or p.get("locations") or [],
                posted_date=_iso(p.get("postedTs")),
                employment_type=(d.get("efcustomTextTimeType") or d.get("type")),
                remote_hint=p.get("workLocationOption"),
                category=p.get("department"),
            )
            seen += 1
            if seen >= max_jobs:
                return
        start += len(pos)


def collect(company, params, http, max_jobs, stats):
    host, domain = params["host"], params["domain"]
    try:
        yield from _v2(company, host, domain, http, max_jobs, stats)
    except Exception as e:
        stats["note"] = f"v2 API failed ({e}); used PCSX API"
        yield from _pcsx(company, host, domain, http, max_jobs, stats)
