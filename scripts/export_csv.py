"""Write the dashboard's Source coverage and Job postings tables as CSV files.

Reads web/data.json (written by build_dataset.py) and writes:
  data/data source.csv   one row per S&P 500 company in scope, with its collection status
  data/Job postings.csv  one row per posting shown on the dashboard, newest first
"""
import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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


def status(c, s):
    if s and s["status"] == "ok":
        return "Collected"
    if s and s["status"] == "blocked":
        return "Blocked by site"
    if s and s["status"] == "empty":
        return "No postings returned"
    if s and s["status"] == "error":
        return "Collector error"
    if c["adapter"] == "none":
        return "Not collected yet"
    return "Collector ready, not yet run"


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

    with open(out_dir / "data source.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Rank", "Ticker", "Company", "Sector", "Career site", "Platform", "Status",
                    "Last collected", "Postings in dashboard", "Listed on site", "Notes"])
        for c in D["companies"]:
            s = latest.get(c["ticker"])
            w.writerow([c["rank"], c["ticker"], c["name"], c.get("sector") or "", c.get("career_site") or "",
                        c["adapter"], status(c, s), s["run_date"] if s else "", by_co.get(c["ticker"], 0),
                        (s or {}).get("site_total") or "", (s and s.get("detail")) or c.get("known_issue") or ""])

    rows.sort(key=lambda r: r["posted"] or "", reverse=True)
    with open(out_dir / "Job postings.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Posting ID", "Title", "Company", "Ticker", "SOC code", "SOC group", "Job level", "Job type",
                    "Work arrangement", "City", "State", "Country", "Number of locations", "Posted", "Pay",
                    "Minimum degree", "Major", "Accepts equivalent experience", "Years of experience", "Skills",
                    "Licenses and certifications", "Status", "Last seen", "URL"])
        for r in rows:
            w.writerow([r["id"], r["title"], names.get(r["co"], r["co"]), r["co"], r["soc"], soc.get(r["soc"], ""),
                        r["lvl"], r["sched"], r["arr"], r["city"] or "", r["state"] or "", r["country"] or "",
                        r["nloc"], r["posted"] or "", posted_pay(r), r["deg"],
                        "; ".join(D.get("majors", [])[i] for i in r.get("major", [])), "Yes" if r["deg_equiv"] else "No",
                        "" if r["yrs"] is None else r["yrs"], "; ".join(skills[i] for i in r["skills"]),
                        "; ".join(D["licenses"][i] for i in r["lic"]),
                        "Open" if r["open"] else "Closed", r.get("last_seen") or "", r["url"]])
    print(f"wrote {len(D['companies'])} companies and {len(rows)} postings to {out_dir}")


if __name__ == "__main__":
    main()
