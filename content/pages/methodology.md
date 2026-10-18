---
title: "Methodology"
page_title: "Methodology"
description: "How JobMarket Lens collects job postings from S&P 500 career sites and turns them into comparable data."
---

How postings are collected, how each field on the dashboard is derived, and what the numbers can and cannot tell you.

## Which companies

All companies in the S&P 500 index except Berkshire Hathaway, which has no company-wide career site. Companies with two share classes are counted once, for 499 companies in all. The list is refreshed when the index changes.

## Where the postings come from

Only from each company's official career site. Where the site runs on a recruiting platform with a public job feed (Workday, Oracle Recruiting Cloud, SAP SuccessFactors, Eightfold, Greenhouse, Lever, iCIMS and others), the collector reads that feed, the same data the career site shows its visitors. Otherwise it reads the structured job information (schema.org JobPosting) published on each posting page.

Collection is polite by design: each site's robots.txt rules are followed, requests are spaced out, and a site's requested crawl delay is respected. When a site refuses automated access, it is recorded as blocked and shown that way on the dashboard. No posting is ever estimated, borrowed from another source, or filled in.

## When it runs

Every Monday at 2:00 a.m. Eastern Time. The dashboard updates when the run finishes, usually a few hours later; the date at the bottom of the dashboard shows the latest update. Each run is a snapshot of the openings listed at that moment.

## Open and closed postings

A posting keeps the date it was first seen. If it is missing from a later successful collection of its company, it is counted as closed and shown with the date it was last seen. If a company's collection fails or the site blocks access, its postings are left as they were rather than being marked closed. For very large employers, collection keeps the newest 3,000 postings per company.

## Which postings are included

Postings dated October 1, 2026 or later. Postings without a date on the career site are left out. A posting dated after the day it was collected (some sites show a scheduled start date) is dated to the collection day.

## How each field is derived

### Occupation

The 2018 Standard Occupational Classification (SOC) major groups, assigned by transparent rules applied to the job title, with the company's own job family as a fallback. Titles the rules cannot place are shown as Unclassified.

### Job level

From title keywords (intern, senior, director and so on), then the company's own level label, then the years of experience required.

### Degree and major required

The lowest degree named in the required qualifications; preferred qualifications are ignored so that nice-to-haves do not raise the minimum. Whether the posting accepts equivalent experience instead is noted. The major is read from the phrase that follows the degree (for example "Bachelor's degree in Computer Science, Engineering, or a related field") and grouped into 30 broad fields of study. About 40% of postings that state a degree also name a major.

### Experience

The first years-of-experience requirement stated in the posting.

### Skills, licenses and certifications

Matched against fixed dictionaries, so a skill or credential that is not in the dictionary will not appear.

### Pay

The range stated in the posting, in its original currency and period. For comparison, ranges in U.S. dollars are annualized (hourly pay × 2,080 hours, monthly pay × 12). Posted ranges are what employers advertise, not what people are actually paid. Many U.S. states and cities now require pay ranges in postings, so disclosure varies by location.

### Work arrangement and schedule

Remote, hybrid or on-site, and full-time, part-time, temporary or internship, as the posting states them.

### Location

The posting's first listed location, split into city, state and country. Postings listing several locations count once.

Whenever a posting does not state something, the field shows "Not specified". Nothing is imputed.

## Limitations

- Postings measure hiring intent, not hires. One posting can fill several positions, and some postings stay open continuously.
- Coverage is not complete: a number of companies are blocked or not yet collected. The Source Coverage table on the dashboard lists every company and its status.
- Companies differ in how much detail they publish, so comparisons of shares (for example, the share disclosing pay) partly reflect writing style, not just requirements.
- Rule-based classification makes occasional mistakes; the rules are kept simple so they can be checked.

## Data files

The company coverage list and all postings shown on the dashboard are published as CSV files in the project's [GitHub repository](https://github.com/yimizhao2015/jobmarket-lens/tree/main/data). The full text of postings is not republished.
