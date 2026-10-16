"""Greenhouse job boards: GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true (one call, all jobs)."""
import html

from .common import html_to_text, raw_posting


def _meta(job, *names):
    for m in job.get("metadata") or []:
        if (m.get("name") or "").lower() in names and m.get("value") not in (None, "", []):
            v = m["value"]
            return ", ".join(map(str, v)) if isinstance(v, list) else str(v)
    return None


def collect(company, params, http, max_jobs, stats):
    data = http.get(f"https://boards-api.greenhouse.io/v1/boards/{params['token']}/jobs", params={"content": "true"}).json()
    jobs = data.get("jobs") or []
    stats["site_total"] = len(jobs)
    # Newest first, so a capped run keeps the most recent postings.
    jobs.sort(key=lambda j: j.get("first_published") or j.get("updated_at") or "", reverse=True)
    for j in jobs[:max_jobs]:
        offices = [o.get("location") or o.get("name") for o in j.get("offices") or []]
        loc = (j.get("location") or {}).get("name")
        yield raw_posting(
            company, j.get("requisition_id") or j["id"], j.get("absolute_url"), j.get("title"),
            # content is HTML that is itself HTML-escaped
            description=html_to_text(html.unescape(j.get("content") or "")),
            locations=[loc] if loc else [o for o in offices if o],
            posted_date=(j.get("first_published") or j.get("updated_at") or "")[:10] or None,
            employment_type=_meta(j, "employment type", "work schedule", "time type", "job type"),
            remote_hint=_meta(j, "workplace type", "remote", "location type", "work arrangement"),
            category=", ".join(d["name"] for d in j.get("departments") or [] if d.get("name")) or None,
        )
