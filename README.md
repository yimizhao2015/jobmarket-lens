# JobMarket Lens

*See demand. Understand skills. Track change.*

Pilot app that collects job postings from the official career sites of the 20 largest S&P 500
companies by index weight, normalizes them, and shows hiring demand by occupation (SOC major group),
skills, education, experience, pay, seniority, schedule, work arrangement and geography.

## Universe (pilot)

First 20 distinct companies by S&P 500 index weight, from Slickcharts, read 2026-10-14. Alphabet's
GOOGL and GOOG share classes count as one company. Listed with weights in `config/companies.json`.

NVIDIA, Apple, Microsoft, Amazon, Alphabet, Meta, Broadcom, Tesla, Berkshire Hathaway, Eli Lilly,
Micron, AMD, Walmart, JPMorgan Chase, Visa, ExxonMobil, Johnson & Johnson, Mastercard, Intel, AbbVie.

## Layout

```
config/companies.json        companies, weights, career sites, which collector each uses
collector/                   one adapter per career-site platform + polite HTTP client + SQLite history
  adapters/workday.py        NVIDIA, Broadcom, Lilly, Micron, Walmart, J&J, Mastercard, Intel, AbbVie
  adapters/amazon.py         amazon.jobs search JSON
  adapters/oracle_hcm.py     JPMorgan Chase (Oracle Recruiting Cloud)
  adapters/eightfold.py      Microsoft
  adapters/smartrecruiters.py  Visa
  adapters/jibe.py           AMD
  adapters/successfactors.py ExxonMobil
  adapters/html_sites.py     Apple, Google, Meta (sitemap + JSON-LD), Tesla
normalize/                   SOC mapping, skills & license dictionaries, field parsers
scripts/build_dataset.py     normalize everything -> web/data.json, web/index.html, data/normalized/postings.csv
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
- The page-read seed sample is used only for companies with no successful collector run, and the
  dashboard labels it as a sample.

## Known gaps

- Collector endpoints were written from each platform's documented/public patterns but could not be
  exercised from the build environment (its network policy blocked the career sites). The first run
  will confirm or correct each; check `run_log.json`.
- Tesla blocks scripted access; Berkshire Hathaway has no company-wide career site (hiring is at
  subsidiaries); Meta's search is a GraphQL app, so the adapter relies on its sitemap.
- Career sites show *currently open* postings. Postings from early 2025 that have already closed are
  not recoverable from these sites; history starts with the first run.
- SOC groups are assigned by title rules (`normalize/soc.py`), not by a trained coder. Skills come from a
  fixed dictionary (`normalize/skills.py`).
