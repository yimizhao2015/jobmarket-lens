# JobMarket Lens

*See demand. Understand skills. Track change.*

JobMarket Lens tracks what America's largest employers are hiring for. It collects job postings from the
official career sites of S&P 500 companies every week, normalizes them, and shows hiring demand by
occupation (SOC major group), skills, education, experience, pay, job level, schedule, work arrangement
and location.

- **Live site:** https://www.jobmarketlens.com/
- **Data files:** [`data/data source.csv`](data/data%20source.csv) (one row per company and its collection
  status) and [`data/Job postings.csv`](data/Job%20postings.csv) (every posting on the dashboard, newest first)

© 2026 Yimi Zhao. All rights reserved. Job postings remain the property of the companies that published them.

## What the dashboard shows

- Filters: year posted, status (open now or closed), company, occupation, job level, work arrangement,
  full/part-time, years of experience, minimum degree, license or certification, country and title text.
- Summary tiles: postings in view, share disclosing pay, median pay, degree requirements, remote/hybrid
  share, full-time share and median years of experience.
- Charts: openings by occupation group and by company, top skills (filterable by occupation), job level,
  minimum degree, experience, work arrangement, full/part-time, licenses, pay ranges, countries, US states,
  and postings over time (weekly bars, switching to monthly once three months are collected).
- Source Coverage: every company in scope and the state of collection from its career site (25 per page).
- Job Postings: the matching postings, newest first (25 per page). A posting that has disappeared from
  the company's site is greyed out with the date it was last seen instead of linking to a dead page.

## Universe

All S&P 500 companies except Berkshire Hathaway, from the Wikipedia constituents list read 2026-10-15;
companies with two share classes count once (499 companies). Each company's career site and the
collector it uses are in `config/companies.json`; companies without a working collector carry a
`known_issue` and show as "Not collected yet".

Only postings dated October 1, 2026 or later are analyzed (`posted_from` in config).

## How the data is collected and stored

```
Weekly run (GitHub Actions on Mondays at 2:00 a.m. Eastern Time, or scripts/run_local.sh on your own computer)
  1. download the posting history (lens.db.gz) from the private repo yimizhao2015/jobmarket-lens-data
  2. collect every company's current postings from its career site       -> data/raw/<date>/
  3. add them to the history: first seen / last seen per posting          -> data/lens.db
  4. normalize and rebuild the dashboard and CSV files                    -> web/index.html, data/*.csv
  5. upload the updated history back to the private repo
  6. commit the dashboard and CSV files here; Vercel republishes the site
```

Collection is incremental. Each company's career site is still listed every week, but a posting already in
the history is not read again: it is written as a short "seen" line and only its last-seen date moves, while
its stored text, fields and first-seen date stay. Only new postings have their detail page requested
(`run_log.json` shows `collected`, all postings listed, and `fetched`, those read in full). The cap of 3,000
per company counts seen postings too, so the open set is the same as a full re-read would give;
`python -m collector.run --full` re-reads everything. Companies run 48 at a time, each with its own paced
client, longest-running first (by their last run's postings and site delay).

The history holds the full text of every posting, so it is kept in the **private** repo
`jobmarket-lens-data` (release `data`) and never in this public repo. The GitHub workflow reaches it with
the `DATA_REPO_TOKEN` secret (a fine-grained token with Contents read/write on that repo); a local run uses
your own `gh` login.

## Layout

```
config/companies.json        companies, career sites, collector per company, collection settings
collector/                   one adapter per career-site platform + polite HTTP client + SQLite history
  http.py                    request pacing, retries, robots.txt (RFC 9309), blocked-site detection
  adapters/workday.py        Workday career sites (most companies)
  adapters/oracle_hcm.py     Oracle Recruiting Cloud
  adapters/successfactors.py SAP SuccessFactors (search pages, or sitemap + page markup)
  adapters/eightfold.py      Eightfold (Microsoft and others)
  adapters/jibe.py           Jibe / iCIMS career sites
  adapters/html_sites.py     any site with a job sitemap + schema.org JobPosting; Apple; refused sites
  adapters/greenhouse.py, lever.py, ashby.py   public job-board APIs
  adapters/icims.py, taleo.py, avature.py, talentbrew.py, jobvite.py   other hosted career sites
  adapters/smartrecruiters.py SmartRecruiters (posting API for Visa; others from their career pages)
  adapters/amazon.py, walmart.py   single-company collectors
  run.py                     runs all companies in parallel, writes data/raw/<date>/run_log.json
normalize/                   SOC mapping, skills & license dictionaries, field parsers
scripts/build_dataset.py     normalize everything -> web/index.html (data embedded), data/normalized/postings.csv
scripts/export_csv.py        "data/data source.csv" and "data/Job postings.csv"
scripts/run_local.sh         the whole weekly run on your own computer
data/seed/                   119 postings read by hand on 2026-10-14 for the pilot (not used: use_seed_sample false)
web/template.html            the dashboard page; build_dataset.py embeds the data into web/index.html
.github/workflows/collect.yml weekly collection (Mondays 2:00 a.m. Eastern, or run it by hand from the Actions tab)
.github/workflows/pages.yml  keeps the old GitHub Pages address redirecting to www.jobmarketlens.com
vercel.json                  Vercel hosting: serves web/ as a static site, redeployed on every push
```

Not in this repo: `data/lens.db` and `data/raw/` (private history), `web/data.json` (build output).

## Run it yourself

On a Mac (Homebrew), once:

```
brew install python git gh
gh auth login            # GitHub.com, HTTPS, log in with a web browser
gh auth setup-git
git clone https://github.com/yimizhao2015/jobmarket-lens.git
```

Then, from the `jobmarket-lens` folder, with the computer plugged in and the lid open:

```
caffeinate -i ./scripts/run_local.sh
```

It takes about 1 to 2 hours and needs about 2 GB of disk space. When it prints "Done", the site redeploys
within a few minutes.

For development without touching the history:

```
pip install -r requirements.txt
python -m collector.run --only AAPL,MSFT --max 20 --date test   # small test run
```

## Rules the pipeline keeps

- Official career sites only. robots.txt is honored using the standard rules (RFC 9309: the most specific
  rule wins), and a site's Crawl-delay is respected. Requests are paced per site (0.6 s by default, 2 s for
  sitemap-based sites, 1.5 s for SuccessFactors). Career sites hosted by Phenom share one firewall, so at most
  three of them are read at a time (`host_groups` in config).
- A site that refuses (robots.txt, HTTP 401/403, bot wall) is recorded as **blocked** and shown as blocked
  on the dashboard. Nothing is estimated or filled in for it, and its postings keep the date they were
  last seen instead of being marked closed.
- A posting missing from a later successful run of its company is marked closed.
- A posted date later than the day the posting was first collected is replaced by that day. Postings with
  no date on the career site are left out.
- Every derived field says "Not specified" when the posting does not state it.
- Pay is the posted range, annualized for comparison; it is not actual earnings.

## Known gaps

- 63 companies are not collected. Each one's `known_issue` in `config/companies.json` says why. Usually
  the site refuses scripted requests (HTTP 403, a bot check, or robots.txt, as on UKG/UltiPro search),
  renders its jobs only in the browser, or runs on a platform without a collector here (Dayforce,
  BrassRing, Paradox, JazzHR, ADP).
- Google (robots.txt disallows its job search), Meta (its robots.txt prohibits automated collection) and
  Tesla (HTTP 403) are recorded as blocked.
- Collection keeps the newest 3,000 postings per company (`max_postings_per_company`).
- Career sites show only *currently open* postings, so history starts with the first run (October 14, 2026).
- SOC groups are assigned by title rules (`normalize/soc.py`), not by a trained coder. Skills and licenses
  come from fixed dictionaries (`normalize/skills.py`), so a skill the dictionary lacks will not appear.
