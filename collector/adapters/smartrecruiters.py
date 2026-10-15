"""SmartRecruiters public Posting API (Visa)."""
from .common import html_to_text, raw_posting

API = "https://api.smartrecruiters.com/v1/companies/{cid}/postings"


def collect(company, params, http, max_jobs, stats):
    cid = params["company_id"]
    offset, seen = 0, 0
    while seen < max_jobs:
        data = http.get(API.format(cid=cid), params={"limit": 100, "offset": offset}).json()
        if offset == 0:
            stats["site_total"] = data.get("totalFound")
        items = data.get("content") or []
        if not items:
            break
        for p in items:
            d = http.get(API.format(cid=cid) + "/" + p["id"]).json()
            sec = (d.get("jobAd") or {}).get("sections") or {}
            desc = "\n".join(filter(None, [html_to_text((sec.get(k) or {}).get("text"))
                                           for k in ("companyDescription", "jobDescription", "qualifications", "additionalInformation")]))
            loc = p.get("location") or {}
            loc_s = ", ".join(filter(None, [loc.get("city"), loc.get("region"), (loc.get("country") or "").upper()]))
            remote = "Remote" if loc.get("remote") else ("Hybrid" if loc.get("hybrid") else None)
            yield raw_posting(
                company, p.get("refNumber") or p["id"], d.get("postingUrl") or f"https://jobs.smartrecruiters.com/{cid}/{p['id']}",
                p.get("name"),
                description=desc or None,
                locations=[loc_s] if loc_s else [],
                posted_date=(p.get("releasedDate") or "")[:10] or None,
                employment_type=(p.get("typeOfEmployment") or {}).get("label"),
                remote_hint=remote,
                category=(p.get("function") or {}).get("label") or (p.get("department") or {}).get("label"),
                level_hint=(p.get("experienceLevel") or {}).get("label"),
            )
            seen += 1
            if seen >= max_jobs:
                return
        offset += len(items)
