"""Normalize everything collected so far and write the dashboard dataset.

    python scripts/build_dataset.py

Inputs:  data/lens.db (from collector runs) and data/seed/*.jsonl (page-read sample, used only for
         companies with no successful collector run yet).
Outputs: web/data.json (compact, for the dashboard), data/normalized/postings.csv (analyst-friendly).
"""
import base64
import csv
import gzip
import json
import sys
from collections import Counter
from multiprocessing import Pool
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from collector import store  # noqa: E402
from normalize import majors, parse, skills, soc  # noqa: E402


def seed_to_raw(s):
    """Turn a page-read seed row into the raw schema so it runs through the same normalizer."""
    bits = []
    if s.get("degree"):
        bits.append(f"Minimum qualifications: {s['degree']}.")
    if s.get("yrs") is not None:
        bits.append(f"{s['yrs']} years of relevant experience.")
    if s.get("skills"):
        bits.append("Skills: " + ", ".join(s["skills"]) + ".")
    if s.get("certs"):
        bits.append("Certifications: " + ", ".join(s["certs"]) + ".")
    return {
        "company": s["co"], "source_id": s["id"], "url": s["url"], "title": s["title"],
        "description": " ".join(bits) or None, "locations": s.get("loc") or [], "posted_date": s.get("posted"),
        "employment_type": s.get("sched"), "remote_hint": "Remote" if s.get("remote") else None,
        "pay_text": s.get("pay"), "category": s.get("cat"), "level_hint": s.get("level"),
        "source_method": "page-read", "first_seen": "2026-10-14", "last_seen": "2026-10-14", "is_open": True,
        "skills_given": s.get("skills") or [], "certs_given": s.get("certs") or [],
    }


def normalize(r):
    text = r.get("description") or ""
    title = r.get("title") or ""
    full = title + "\n" + text
    yrs = parse.parse_years(text)
    deg, deg_equiv = parse.parse_degree(text)
    pay = parse.parse_pay(r.get("pay_text"), text)
    code, rule = soc.classify(title, r.get("category"))
    sk = skills.find_skills(full)
    for given in r.get("skills_given", []):  # page-read rows: map each listed skill to the dictionary
        sk += [s for s in skills.find_skills(given) if s not in sk]
    lic = skills.find_licenses(text + " " + " ".join(r.get("certs_given", [])))
    major = majors.find_majors(text)
    locs = r.get("locations") or []
    country, state, city = parse.parse_location(locs[0]) if locs else (None, None, None)
    posted = r.get("posted_date")
    basis = "posted"
    if not posted:
        posted, basis = r.get("first_seen"), "first_seen"
    elif r.get("first_seen") and posted > r["first_seen"]:
        # Some sites give a scheduled start date or a next-day local date; a posting live when we
        # collected it was posted no later than that day.
        posted, basis = r["first_seen"], "first_seen"
    return {
        "id": f"{r['company']}:{r['source_id']}",
        "co": r["company"],
        "title": title,
        "url": r.get("url"),
        "posted": posted,
        "date_basis": basis,
        "year": int(posted[:4]) if posted else None,
        "month": posted[:7] if posted else None,
        "first_seen": r.get("first_seen"),
        "last_seen": r.get("last_seen"),
        "open": bool(r.get("is_open")),
        "soc": code,
        "soc_rule": rule,
        "category": r.get("category"),
        "sched": parse.parse_schedule(r.get("employment_type"), title, text),
        "arr": parse.parse_arrangement(r.get("remote_hint"), locs, text),
        "deg": deg,
        "deg_equiv": deg_equiv,
        "yrs": yrs,
        "yrs_b": parse.years_bucket(yrs),
        "lvl": parse.parse_level(title, r.get("level_hint"), yrs),
        "pay_min": pay["annual_min"] if pay else None,
        "pay_max": pay["annual_max"] if pay else None,
        "pay_lo": pay["min"] if pay else None,
        "pay_hi": pay["max"] if pay else None,
        "pay_period": pay["period"] if pay else None,
        "pay_cur": pay["currency"] if pay else None,
        "country": country or parse.NS,
        "state": state,
        "city": city,
        "nloc": len(locs),
        "skills": sk,
        "lic": lic,
        "major": major,
        "src": r.get("source_method", "api"),
        "has_text": bool(r.get("description")),
    }


def main():
    cfg = json.loads((ROOT / "config/companies.json").read_text())
    col = cfg["collection"]
    rows, snaps = ([], [])
    if (ROOT / "data/lens.db").exists():
        rows, snaps = store.load_postings(ROOT)
    collected = {r["company"] for r in rows}
    seed_rows = []
    for f in sorted((ROOT / "data/seed").glob("*.jsonl")):
        for line in f.open():
            s = json.loads(line)
            if col.get("use_seed_sample") and s["co"] not in collected:
                seed_rows.append(seed_to_raw(s))

    dropped, undated, keep = Counter(), Counter(), []
    for r in rows + seed_rows:
        posted = r.get("posted_date")
        if not posted:  # no posting date on the site: can't place it in the date window
            undated[r["company"]] += 1
            continue
        if r.get("first_seen") and posted > r["first_seen"]:
            posted = r["first_seen"]  # same clamp normalize() applies
        if not (col["posted_from"] <= posted[:10] <= (col.get("posted_to") or "9999-12-31")):
            dropped[r["company"]] += 1
            continue
        keep.append(r)
    # Normalizing is regex-heavy; spread it over the machine's cores.
    with Pool() as pool:
        out = pool.map(normalize, keep, chunksize=200)

    # Compact encoding: repeated strings become indexes into lookup tables.
    skill_names = sorted({s for n in out for s in n["skills"]})
    lic_names = sorted({s for n in out for s in n["lic"]})
    sk_ix = {s: i for i, s in enumerate(skill_names)}
    lic_ix = {s: i for i, s in enumerate(lic_names)}
    major_ix = {s: i for i, s in enumerate(majors.NAMES)}
    fields = ["id", "co", "title", "url", "posted", "year", "month", "open", "soc", "sched", "arr", "deg",
              "deg_equiv", "yrs", "yrs_b", "lvl", "pay_min", "pay_max", "pay_lo", "pay_hi", "pay_period", "pay_cur", "country",
              "state", "city", "nloc", "src", "first_seen", "last_seen"]
    data = {
        "generated": date.today().isoformat(),
        "posted_from": col["posted_from"],
        "universe": cfg["universe"],
        "companies": [{k: c.get(k) for k in ("rank", "ticker", "name", "weight_pct", "sector", "career_site",
                                             "adapter", "known_issue")} for c in cfg["companies"]],
        "soc_major": soc.SOC_MAJOR,
        "levels": parse.LEVELS,
        "degree_order": parse.DEGREE_ORDER,
        "skills": [{"name": s, "family": skills.SKILL_FAMILY.get(s, "Other")} for s in skill_names],
        "licenses": lic_names,
        "majors": majors.NAMES,
        "snapshots": snaps,
        "fields": fields + ["skills", "lic", "major"],
        "rows": [[n[f] for f in fields] + [[sk_ix[s] for s in n["skills"]], [lic_ix[s] for s in n["lic"]],
                                           [major_ix[s] for s in n["major"]]] for n in out],
        "dropped_outside_window": dict(dropped),
        "dropped_undated": dict(undated),
    }
    (ROOT / "web").mkdir(exist_ok=True)
    (ROOT / "web/data.json").write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False))

    # Dashboard pages with the data inlined: index.html opens straight from disk; artifact.html is the
    # body-only variant used for publishing.
    tpl = (ROOT / "web/template.html").read_text()
    raw_json = json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode()
    payload = json.dumps(base64.b64encode(gzip.compress(raw_json, 9)).decode())
    body = tpl.replace("/*DATA*/null", payload)
    (ROOT / "web/artifact.html").write_text(body)
    (ROOT / "web/index.html").write_text(
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"></head>\n'
        '<body style="margin:0">\n' + body + "\n</body></html>\n")

    (ROOT / "data/normalized").mkdir(parents=True, exist_ok=True)
    with open(ROOT / "data/normalized/postings.csv", "w", newline="") as f:
        cols = list(out[0].keys()) if out else []
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for n in out:
            w.writerow({**n, "skills": "; ".join(n["skills"]), "lic": "; ".join(n["lic"]), "major": "; ".join(n["major"])})

    by_co = Counter(n["co"] for n in out)
    print(f"{len(out)} postings in window; by company: {dict(by_co)}; dropped: {dict(dropped)}")
    print("SOC:", Counter(n["soc"] for n in out).most_common())
    print("unclassified titles:", [n["title"] for n in out if n["soc"] == "00"][:20])

    # CSV copies of the Source coverage and Job postings tables, kept in the repo.
    import export_csv
    export_csv.main()


if __name__ == "__main__":
    main()
