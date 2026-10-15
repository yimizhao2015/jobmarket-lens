"""Oracle Recruiting Cloud candidate-experience REST API (JPMorgan Chase)."""
from .common import html_to_text, raw_posting

LIST = ("https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
        "?onlyData=true&expand=requisitionList.secondaryLocations"
        "&finder=findReqs;siteNumber={site},limit=25,offset={offset},sortBy=POSTING_DATES_DESC")
DETAIL = ("https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails"
          "?expand=all&onlyData=true&finder=ById;Id=%22{id}%22,siteNumber={site}")


def collect(company, params, http, max_jobs, stats):
    host, site = params["host"], params["site_number"]
    offset, seen = 0, 0
    while seen < max_jobs:
        data = http.get(LIST.format(host=host, site=site, offset=offset)).json()
        items = (data.get("items") or [{}])[0]
        if offset == 0:
            stats["site_total"] = items.get("TotalJobsCount")
        reqs = items.get("requisitionList") or []
        if not reqs:
            break
        for q in reqs:
            jid = q.get("Id")
            try:
                d = (http.get(DETAIL.format(host=host, site=site, id=jid)).json().get("items") or [{}])[0]
            except Exception:
                stats["detail_errors"] = stats.get("detail_errors", 0) + 1
                d = {}
            desc = "\n".join(filter(None, [html_to_text(d.get(k)) for k in
                                           ("ExternalDescriptionStr", "ExternalResponsibilitiesStr", "ExternalQualificationsStr")]))
            locs = [q.get("PrimaryLocation")] + [s.get("Name") for s in (q.get("secondaryLocations") or [])]
            yield raw_posting(
                company, jid, f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{jid}",
                q.get("Title"),
                description=desc or None,
                locations=[l for l in locs if l],
                posted_date=(q.get("PostedDate") or "")[:10] or None,
                employment_type=d.get("JobSchedule") or q.get("JobSchedule"),
                remote_hint=q.get("WorkplaceType") or d.get("WorkplaceType"),
                category=q.get("JobFamily") or d.get("JobFamily"),
                level_hint=d.get("JobLevel"),
            )
            seen += 1
            if seen >= max_jobs:
                return
        offset += len(reqs)
