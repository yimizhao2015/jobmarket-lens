from . import amazon, eightfold, html_sites, jibe, oracle_hcm, smartrecruiters, successfactors, walmart, workday

ADAPTERS = {
    "workday": workday.collect,
    "amazon": amazon.collect,
    "oracle_hcm": oracle_hcm.collect,
    "eightfold": eightfold.collect,
    "smartrecruiters": smartrecruiters.collect,
    "jibe": jibe.collect,
    "successfactors": successfactors.collect,
    "apple": html_sites.collect_apple,
    "google": html_sites.collect_google,
    "jsonld_sitemap": html_sites.collect_sitemap,
    "tesla": html_sites.collect_tesla,
    "walmart": walmart.collect,
    "refused_by_terms": html_sites.collect_refused_by_terms,
}
