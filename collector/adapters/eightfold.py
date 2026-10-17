"""Eightfold career sites (Microsoft). Tries the v2 apply API, then the newer PCSX API."""
import time
from datetime import datetime, timezone

import requests

from .common import html_to_text, raw_posting, seen_before


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
            rec = seen_before(company, http, source_id=p.get("display_job_id") or p["id"])
            if rec:  # already in the history: no detail request
                yield rec
                seen += 1
                if seen >= max_jobs:
                    return
                continue
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


def _search(http, host, params):
    # After many requests the PCSX search answers 405 for a while; wait it out rather than lose the run.
    for wait in (60, 180, 0):
        try:
            return http.get(f"https://{host}/api/pcsx/search", params=params).json()
        except requests.HTTPError as e:
            if e.response is None or e.response.status_code != 405 or not wait:
                raise
            time.sleep(wait)


def _pcsx(company, host, domain, http, max_jobs, stats):
    start, seen = 0, 0
    while seen < max_jobs:
        data = _search(http, host, {"domain": domain, "start": start, "num": 10, "sort_by": "timestamp", "query": ""})
        data = data.get("data", data)
        if start == 0:
            stats["site_total"] = data.get("count")
        pos = data.get("positions") or []
        if not pos:
            break
        for p in pos:
            rec = seen_before(company, http, source_id=p.get("displayJobId") or p["id"])
            if rec:  # already in the history: no detail request
                yield rec
                seen += 1
                if seen >= max_jobs:
                    return
                continue
            try:
                d = http.get(f"https://{host}/api/pcsx/position_details",
                             params={"position_id": p["id"], "domain": domain}).json()
            except requests.HTTPError:  # closed between the search and the detail request; skip it
                continue
            d = d.get("data", d)
            yield raw_posting(
                company, p.get("displayJobId") or p["id"], f"https://{host}/careers/job/{p['id']}",
                p.get("name"),
                description=html_to_text(d.get("jobDescription")),
                locations=p.get("standardizedLocations") or p.get("locations") or [],
                posted_date=_iso(p.get("postedTs") or p.get("creationTs")),  # postedTs is 0 on some sites
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
