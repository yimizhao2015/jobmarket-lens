"""Jobvite career sites. The job list on jobs.jobvite.com/{site} is drawn in the browser and the job pages carry
no posted date, so postings come from Jobvite's public job feed for the company:
GET https://app.jobvite.com/CompanyJobs/Xml.aspx?c={company_id} (one <job> per open posting, with its date)."""
import xml.etree.ElementTree as ET
from datetime import datetime

from .common import html_to_text, raw_posting


def _date(v):
    try:
        return datetime.strptime((v or "").strip(), "%m/%d/%Y").date().isoformat()
    except ValueError:
        return None


def collect(company, params, http, max_jobs, stats):
    root = ET.fromstring(http.get("https://app.jobvite.com/CompanyJobs/Xml.aspx", params={"c": params["company_id"]}).content)
    jobs = [{c.tag: (c.text or "").strip() for c in j} for j in root.iter("job")]
    stats["site_total"] = len(jobs)
    jobs.sort(key=lambda j: _date(j.get("date")) or "", reverse=True)
    for j in jobs[:max_jobs]:
        url = f"https://jobs.jobvite.com/{params['site']}/job/{j['id']}" if params.get("site") else j.get("detail-url")
        yield raw_posting(
            company, j.get("requisitionid") or j["id"], url, j.get("title"),
            description=html_to_text(j.get("description")),
            locations=[j["location"]] if j.get("location") else [],
            posted_date=_date(j.get("date")),
            employment_type=j.get("jobtype") or None,
            category=j.get("category") if j.get("category") not in (None, "", "Unknown") else None,
        )
