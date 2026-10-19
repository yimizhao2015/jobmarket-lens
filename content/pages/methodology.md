---
title: "Methodology"
page_title: "Methodology"
description: "How JobMarket Lens collects job postings from S&P 500 career sites and turns them into comparable data."
---

How postings are collected, how each field is derived, and what the numbers can and cannot tell you.

## Collection

- **Companies:** all S&P 500 companies except Berkshire Hathaway; companies with two share classes count once (499 in all).
- **Sources:** each company's official career site only, read through its recruiting platform's public job feed or the structured job data on each posting page.
- **Rules:** robots.txt and crawl delays are respected. A site that refuses access is recorded as blocked; nothing is estimated or filled in.
- **Schedule:** every Sunday at 5:00 p.m. Eastern Time, so each Monday-to-Sunday week is complete. The date at the bottom of the dashboard shows the latest update.
- **Scope:** postings dated October 1, 2026 or later, up to the newest 3,000 per company. Postings without a date are left out. Collection began on October 14, 2026, and the first full collection covering every reachable company was on October 16, 2026. Postings dated before then are included only if they were still listed at that point, so the first weeks may undercount postings that closed quickly.
- **Open and closed:** a posting missing from a later successful collection of its company is marked closed, with the date it was last seen.

## Fields

| Field | How it is derived |
| --- | --- |
| Occupation | 2018 SOC major group, from rules applied to the job title (company job family as fallback); otherwise Unclassified |
| Job level | Title keywords, then the company's level label, then years of experience |
| Degree and major | Lowest degree in the required qualifications, and the fields of study named after it, grouped into 30 broad majors |
| Experience | The first years-of-experience requirement stated |
| Skills, licenses | Matched against fixed dictionaries |
| Pay | The posted range; U.S. dollar ranges are annualized for comparison (hourly × 2,080, monthly × 12) |
| Work arrangement, schedule | Remote, hybrid or on-site; full-time, part-time, temporary or internship, as stated |
| Location | The first listed location, split into city, state and country |

Anything a posting does not state shows as "Not specified".

## Limitations

- Postings measure hiring intent, not hires.
- Coverage is incomplete; the Source Coverage table on the dashboard shows each company's status.
- Companies differ in how much detail they publish, and rule-based classification makes occasional mistakes.
- Posted pay ranges are what employers advertise, not what people earn.
