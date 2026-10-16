# JobMarket Lens

*See demand. Understand skills. Track change.*

Collects job postings from the official career sites of S&P 500 companies, normalizes them, and shows
hiring demand by occupation (SOC major group), skills, education, experience, pay, seniority, schedule,
work arrangement and geography. Live site: https://yimizhao2015.github.io/jobmarket-lens/

## Universe

All S&P 500 companies except Berkshire Hathaway (no company-wide career site), from the Wikipedia
constituents list read 2026-10-15; companies with two share classes count once (499 companies). The
first 20 are the original pilot companies in index-weight order. Each company's career site and the
collector it uses are in `config/companies.json`; companies without a working collector carry a
`known_issue` and show as "not collected" on the dashboard.

## Layout

```
config/companies.json        companies, weights, career sites, which collector each uses
collector/                   one adapter per career-site platform + polite HTTP client + SQLite history
  adapters/workday.py        Workday career sites (most companies)
  adapters/oracle_hcm.py     Oracle Recruiting Cloud
  adapters/successfactors.py SAP SuccessFactors (search pages, or sitemap + page markup)
  adapters/eightfold.py      Eightfold (Microsoft and others)
  adapters/jibe.py           Jibe / iCIMS career sites
  adapters/html_sites.py     any site with a job sitemap + schema.org JobPosting; Apple; blocked sites
  adapters/amazon.py, walmart.py, smartrecruiters.py   single-company collectors
normalize/                   SOC mapping, skills & license dictionaries, field parsers
scripts/build_dataset.py     normalize everything -> web/data.json, web/index.html, data/normalized/postings.csv
scripts/export_csv.py        Source coverage and Job postings tables -> "data/data source.csv", "data/Job postings.csv"
data/seed/                   119 postings read by hand from 4 career sites on 2026-10-14 (pilot sample)
data/raw/<date>/             raw JSONL per company per run + run_log.json
data/lens.db                 history: first_seen / last_seen per posting, per-run totals
web/index.html               the dashboard (open directly in a browser)
```

## Run

Needs Python 3.10+ with `requests` and `beautifulsoup4`, and network access to the career sites.

```
pip install requests beautifulsoup4
python -m collector.run --max 50          # quick smoke test, 50 postings per company
python -m collector.run                   # full run (cap per company in config, default 800)
python scripts/build_dataset.py           # rebuild dashboard data
open web/index.html
```

Run the collector on a schedule (weekly or monthly) to build the "track change" history: each run is a
snapshot; postings missing from a later run are marked closed.

## Rules the pipeline keeps

- Official career sites only. robots.txt is honored; a site that refuses (robots, 403, bot wall) is
  logged as **blocked** in `run_log.json` and shown as blocked on the dashboard. Nothing is estimated
  or filled in for it.
- Only postings dated 2026-10-01 to 2026-12-31 are analyzed (`posted_from` / `posted_to` in config). A posted date later than
  the day the posting was first collected is replaced by that day.
- Every derived field says "Not specified" when the posting does not state it.
- Postings with no date on the career site are left out, since they can't be placed in the date window.
- The hand-read seed sample in `data/seed/` is not used (`use_seed_sample: false`).

## Known gaps

- About 150 companies have no collector yet: their career platform wasn't identified automatically, or
  it is one without a collector here (Taleo, Avature, iCIMS classic, UltiPro, Greenhouse and others).
- Google (robots.txt disallows its job search), Meta (robots.txt prohibits automated collection) and
  Tesla (HTTP 403) are recorded as blocked.
- Collection keeps the newest 800 postings per company (`max_postings_per_company`).
- Career sites show *currently open* postings; history starts with the first run.
- SOC groups are assigned by title rules (`normalize/soc.py`), not by a trained coder. Skills come from a
  fixed dictionary (`normalize/skills.py`).
