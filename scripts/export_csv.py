"""Write the CSV copies of the Source coverage and Job postings tables, and the free sample.

Reads web/data.json (written by build_dataset.py) and writes:
  data/data source.csv   one row per S&P 500 company in scope, with its collection status
  data/collection status by week.csv
                         one row per company, one column per posted week: its postings that week, or "blocked",
                         "error" or "not collected" when the run(s) right after the week did not succeed
  data/Job postings/Job postings YYYY-MM part N.csv
                         one row per posting, newest first, one file per month posted, in parts of ROWS_PER_FILE
  web/downloads/jobmarketlens-sample.csv         1,000 random postings, free on the site
The CSV files under data/ are not committed to this public repo. CSV files start with a UTF-8 byte order mark so Excel opens them with the right characters.
"""
import csv
import json
import random
from datetime import date, timedelta
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROWS_PER_FILE = 75_000  # about 32 MB
SAMPLE_ROWS = 1_000
ENC = "utf-8-sig"
NS = "Not specified"


def posted_pay(r):
    if r["pay_lo"] is None:
        return NS
    sym = "$" if r["pay_cur"] in ("USD", None, "") else r["pay_cur"] + " "
    dec = 2 if r["pay_period"] == "hour" else 0
    f = lambda v: f"{sym}{v:,.{dec}f}"
    amt = f(r["pay_lo"]) if r["pay_lo"] == r["pay_hi"] else f"{f(r['pay_lo'])}–{f(r['pay_hi'])}"
    per = {"hour": "per hour", "month": "per month", "year": "per year"}.get(r["pay_period"], "")
    return f"{amt} {per}".strip()


def long(iso):
    """2026-10-05 -> October 5, 2026"""
    d = date.fromisoformat(iso)
    return f"{d:%B} {d.day}, {d.year}"


def status(c, s):
    if s and s["status"] == "ok":
        return "Collected"
    if s and s["status"] == "blocked":
        return "Blocked by site"
    if s and s["status"] == "empty":
        return "No postings returned"
    if s and s["status"] == "error":
        return "Collector error"
    if c.get("coverage") == "blocked":
        return "Blocked by site"
    if c.get("coverage") == "no_job_board":
        return "No online job board"
    if c["adapter"] == "none":
        return "Not collected yet"
    return "Collector ready, not yet run"


STATUS_LABEL = {"blocked": "blocked", "error": "error", "not_applicable": "not collected"}


def weekly_status(D, rows, path):
    """Collection status by week: the postings each company posted in each Monday-to-Sunday week, or the status of
    the run(s) in the week after it (the runs that collected it) when none of them succeeded, with any postings
    that arrived in another run in parentheses. Workday's security check (HTTP 429) counts as blocked."""
    first = date.fromisoformat(D["posted_from"])
    last = date.fromisoformat(D["posted_to"])
    weeks = [first + timedelta(weeks=i) for i in range((last - first).days // 7 + 1)]
    count = Counter()
    for r in rows:
        if r["posted"]:
            d = date.fromisoformat(r["posted"][:10])
            count[r["co"], d - timedelta(days=d.weekday())] += 1
    runs = {}
    for s in sorted(D.get("snapshots") or [], key=lambda s: s["run_date"]):
        st, det = s["status"], s.get("detail") or ""
        if st == "error" and ("429" in det or "security check" in det):
            st = "blocked"
        runs.setdefault(s["company"], []).append((date.fromisoformat(s["run_date"]), st, det))

    def cell(t, wk):
        n = count[t, wk]
        # The runs that collected this week: those in the following week (the first week also counts the
        # first collections, made before its end)
        sts = [st for d, st, _ in runs.get(t, [])
               if wk + timedelta(days=7) <= d <= wk + timedelta(days=13) or (wk == weeks[0] and d < wk + timedelta(days=7))]
        if not sts or any(st in ("ok", "empty") for st in sts):
            return n
        label = STATUS_LABEL.get(sts[-1], sts[-1])
        return f"{label} ({n})" if n else label

    with open(path, "w", newline="", encoding=ENC) as f:
        w = csv.writer(f)
        w.writerow(["Company name", "Ticker"] + [f"{wk:%b}-{wk.day}-{wk.year}" for wk in weeks]
                   + ["Latest run", "Latest status", "Note"])
        for c in sorted(D["companies"], key=lambda c: c["rank"]):
            t = c["ticker"]
            d, st, det = (runs.get(t) or [(None, "", "")])[-1]
            w.writerow([c["name"], t] + [cell(t, wk) for wk in weeks]
                       + [d or "", STATUS_LABEL.get(st, st), det or c.get("known_issue") or ""])


def main():
    D = json.loads((ROOT / "web/data.json").read_text())
    rows = [dict(zip(D["fields"], r)) for r in D["rows"]]
    by_co = Counter(r["co"] for r in rows)
    latest = {}
    for s in D.get("snapshots") or []:
        latest[s["company"]] = s
    names = {c["ticker"]: c["name"] for c in D["companies"]}
    soc = {**D["soc_major"], "00": D["soc_major"].get("00", "Unclassified")}
    skills = [s["name"] for s in D["skills"]]
    out_dir = ROOT / "data"
    out_dir.mkdir(exist_ok=True)

    with open(out_dir / "data source.csv", "w", newline="", encoding=ENC) as f:
        w = csv.writer(f)
        w.writerow(["Rank", "Ticker", "Company", "Sector", "Career site", "Platform", "Status",
                    "Last collected", "Postings in dashboard", "Listed on site", "Notes"])
        for c in D["companies"]:
            s = latest.get(c["ticker"])
            w.writerow([c["rank"], c["ticker"], c["name"], c.get("sector") or "", c.get("career_site") or "",
                        c["adapter"], status(c, s), s["run_date"] if s else "", by_co.get(c["ticker"], 0),
                        (s or {}).get("site_total") or "", (s and s.get("detail")) or c.get("known_issue") or ""])

    weekly_status(D, rows, out_dir / "collection status by week.csv")

    rows.sort(key=lambda r: r["posted"] or "", reverse=True)
    header = ["Posting ID", "Title", "Company", "Ticker", "SOC code", "SOC group", "Job level", "Job type",
              "Work arrangement", "City", "State", "Country", "Number of locations", "Posted", "Pay",
              "Minimum degree", "Major", "Accepts equivalent experience", "Years of experience", "Skills",
              "Licenses and certifications", "Status", "Last seen", "URL"]
    by_month = {}
    for r in rows:
        by_month.setdefault((r["posted"] or "undated")[:7], []).append(r)
    post_dir = out_dir / "Job postings"
    post_dir.mkdir(exist_ok=True)
    for old in post_dir.glob("*.csv"):
        old.unlink()
    (out_dir / "Job postings.csv").unlink(missing_ok=True)  # the single file used before the split
    def row(r):
        return [r["id"], r["title"], names.get(r["co"], r["co"]), r["co"], r["soc"], soc.get(r["soc"], ""),
                r["lvl"], r["sched"], r["arr"], r["city"] or "", r["state"] or "", r["country"] or "",
                r["nloc"], r["posted"] or "", posted_pay(r), r["deg"],
                "; ".join(D.get("majors", [])[i] for i in r.get("major", [])),
                "Yes" if r["deg_equiv"] else "No",
                "" if r["yrs"] is None else r["yrs"], "; ".join(skills[i] for i in r["skills"]),
                "; ".join(D["licenses"][i] for i in r["lic"]),
                "Open" if r["open"] else "Closed", r.get("last_seen") or "", r["url"]]

    def write(path, some):
        with open(path, "w", newline="", encoding=ENC) as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(row(r) for r in some)

    for month, month_rows in by_month.items():
        for part, start in enumerate(range(0, len(month_rows), ROWS_PER_FILE), 1):
            write(post_dir / f"Job postings {month} part {part}.csv", month_rows[start:start + ROWS_PER_FILE])

    run = max((s["run_date"] for s in latest.values() if s.get("run_date")), default="")

    # Free sample: 1,000 postings drawn at random (the same draw all week), sorted by company and date.
    sample = random.Random(run).sample(rows, min(SAMPLE_ROWS, len(rows)))
    sample.sort(key=lambda r: (names.get(r["co"], r["co"]), r["posted"] or ""))
    (ROOT / "web/downloads").mkdir(exist_ok=True)
    write(ROOT / "web/downloads/jobmarketlens-sample.csv", sample)
    print(f"wrote {len(D['companies'])} companies and {len(rows)} postings to {out_dir}")


if __name__ == "__main__":
    main()
