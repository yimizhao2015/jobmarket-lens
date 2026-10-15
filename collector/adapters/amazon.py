"""amazon.jobs public search JSON: GET /en/search.json?result_limit=100&offset=N&sort=recent"""
from datetime import datetime

from .common import html_to_text, raw_posting


def _date(s):
    try:
        return datetime.strptime(s.strip(), "%B %d, %Y").date().isoformat()
    except (AttributeError, ValueError):
        return None


def collect(company, params, http, max_jobs, stats):
    offset, seen = 0, 0
    while seen < max_jobs:
        r = http.get("https://www.amazon.jobs/en/search.json",
                     params={"result_limit": 100, "offset": offset, "sort": "recent"})
        data = r.json()
        if offset == 0:
            stats["site_total"] = data.get("hits")
        jobs = data.get("jobs") or []
        if not jobs:
            break
        for j in jobs:
            text = "\n".join(filter(None, [
                html_to_text(j.get("description")),
                "Basic qualifications:\n" + html_to_text(j.get("basic_qualifications") or "") ,
                "Preferred qualifications:\n" + html_to_text(j.get("preferred_qualifications") or ""),
            ]))
            loc = ", ".join(filter(None, [j.get("city"), j.get("state"), j.get("country_code")])) or j.get("location")
            yield raw_posting(
                company, j.get("id_icims") or j.get("id"), "https://www.amazon.jobs" + (j.get("job_path") or ""),
                j.get("title"),
                description=text,
                locations=[loc] if loc else [],
                posted_date=_date(j.get("posted_date")),
                employment_type=j.get("job_schedule_type"),
                category=j.get("job_category"),
            )
            seen += 1
            if seen >= max_jobs:
                return
        offset += len(jobs)
