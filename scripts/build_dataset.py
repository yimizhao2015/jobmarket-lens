"""Normalize everything collected so far and write the dashboard dataset.

    python scripts/build_dataset.py

Input:   data/lens.db (from collector runs).
Outputs: web/data.json (compact, for the dashboard), data/normalized/postings.csv (analyst-friendly).
"""
import base64
import csv
import gzip
import hashlib
import json
import sqlite3
import sys
from collections import Counter
from multiprocessing import Pool
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from collector import store  # noqa: E402
from normalize import majors, parse, skills, soc  # noqa: E402


# Reading a posting's text (skills, degree, pay, ...) is most of the build's time, and a posting's text rarely
# changes from week to week. Those results are kept in data/norm_cache.db (saved beside lens.db), keyed by a hash
# of the fields they read plus the normalize/ code, so only new or changed postings, or all of them after a
# dictionary or rule change, are read again. Dates, open/closed and locations are worked out fresh every build.
CACHE = ROOT / "data/norm_cache.db"
TEXT_INPUTS = ("title", "description", "pay_text", "category", "employment_type", "remote_hint", "locations",
               "level_hint", "skills_given", "certs_given")


def code_version():
    h = hashlib.sha256()
    for f in sorted((ROOT / "normalize").rglob("*.py")) + [Path(__file__)]:
        h.update(f.read_bytes())
    return h.hexdigest()[:16]


def text_key(r, version):
    blob = json.dumps([r.get(k) for k in TEXT_INPUTS], ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha1((version + blob).encode()).hexdigest()


def read_text(r):
    """The fields that come from the posting's own text: the slow part, cached."""
    text = r.get("description") or ""
    title = r.get("title") or ""
    full = title + "\n" + text
    locs = r.get("locations") or []
    yrs = parse.parse_years(text)
    deg, deg_equiv = parse.parse_degree(text)
    pay = parse.parse_pay(r.get("pay_text"), text)
    code, rule = soc.classify(title, r.get("category"))
    sk = skills.find_skills(full)
    for given in r.get("skills_given", []):  # page-read rows: map each listed skill to the dictionary
        sk += [s for s in skills.find_skills(given) if s not in sk]
    lic = skills.find_licenses(text + " " + " ".join(r.get("certs_given", [])))
    return {
        "soc": code,
        "soc_rule": rule,
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
        "skills": sk,
        "lic": lic,
        "major": majors.find_majors(text),
    }


TEXT_FIELDS = ("soc", "soc_rule", "sched", "arr", "deg", "deg_equiv", "yrs", "yrs_b", "lvl", "pay_min", "pay_max",
               "pay_lo", "pay_hi", "pay_period", "pay_cur", "skills", "lic", "major")


def normalize(r):
    """One posting's dashboard row; r["cached"] holds read_text(r) from an earlier build when there is one.
    Returns (row, read_text result when it was computed here, else None)."""
    cached = r.get("cached")
    t = cached if cached is not None else read_text(r)
    title = r.get("title") or ""
    locs = r.get("locations") or []
    country, state, city = parse.parse_location(locs[0], set(r.get("prefer") or ())) if locs else (None, None, None)
    posted = r.get("posted_date")
    basis = "posted"
    if not posted:
        posted, basis = r.get("first_seen"), "first_seen"
    elif r.get("first_seen") and posted > r["first_seen"]:
        # Some sites give a scheduled start date or a next-day local date; a posting live when we
        # collected it was posted no later than that day.
        posted, basis = r["first_seen"], "first_seen"
    return _ordered({
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
        "category": r.get("category"),
        "country": country or parse.NS,
        "state": state,
        "city": city,
        "nloc": len(locs),
        "src": r.get("source_method", "api"),
        "has_text": bool(r.get("description")),
    }, t), (None if cached is not None else t)


# The row's field order (also postings.csv's column order)
ORDER = ("id", "co", "title", "url", "posted", "date_basis", "year", "month", "first_seen", "last_seen", "open", "soc",
         "soc_rule", "category", "sched", "arr", "deg", "deg_equiv", "yrs", "yrs_b", "lvl", "pay_min", "pay_max",
         "pay_lo", "pay_hi", "pay_period", "pay_cur", "country", "state", "city", "nloc", "skills", "lic", "major",
         "src", "has_text")


def _ordered(base, text):
    both = {**base, **text}
    return {k: both[k] for k in ORDER}


def main():
    # Normalizing is regex-heavy, so it is spread over the machine's cores. The workers start before the history
    # is loaded: forked later, each would end up with its own copy of every posting's text, and the runner
    # ran out of memory (Nov 2, 2026).
    with Pool() as pool:
        build(pool)


def build(pool):
    cfg = json.loads((ROOT / "config/companies.json").read_text())
    col = cfg["collection"]
    rows, snaps = ([], [])
    if (ROOT / "data/lens.db").exists():
        # postings dated before the window can't be in it (normalize only moves dates earlier)
        rows, snaps = store.load_postings(ROOT, since=col["posted_from"])

    # The window ends with the last complete Monday-to-Sunday week: the Sunday on or before the latest
    # run (the run itself is early Monday), so a partly collected week is never shown.
    last_run = max((s["run_date"] for s in snaps), default=date.today().isoformat())
    lr = date.fromisoformat(last_run)
    posted_to = (lr - timedelta(days=(lr.weekday() + 1) % 7)).isoformat()
    if col.get("posted_to"):
        posted_to = min(posted_to, col["posted_to"])

    dropped, undated, keep = Counter(), Counter(), []
    if (ROOT / "data/lens.db").exists():
        dropped.update(store.count_before(ROOT, col["posted_from"]))
    for r in rows:
        posted = r.get("posted_date")
        if not posted:  # no posting date on the site: can't place it in the date window
            undated[r["company"]] += 1
            continue
        if r.get("first_seen") and posted > r["first_seen"]:
            posted = r["first_seen"]  # same clamp normalize() applies
        if not (col["posted_from"] <= posted[:10] <= posted_to):
            dropped[r["company"]] += 1
            continue
        keep.append(r)
    del rows  # postings outside the window are no longer needed
    # The countries each company's other locations clearly name; a bare city name found in several
    # countries ("Hyderabad", "San Jose") is settled toward these
    seen = Counter()
    for r in keep:
        locs = r.get("locations") or []
        country = parse.parse_location(locs[0])[0] if locs else None
        if country:
            seen[r["company"], country] += 1
    prefer = {}
    for (co, country), n in seen.items():
        if n >= 3:
            prefer.setdefault(co, []).append(country)
    for r in keep:
        r["prefer"] = prefer.get(r["company"])
    version = code_version()
    cache = sqlite3.connect(CACHE)
    cache.execute("CREATE TABLE IF NOT EXISTS text (key TEXT PRIMARY KEY, val TEXT)")
    keys = [text_key(r, version) for r in keep]
    for i in range(0, len(keep), 900):
        part = keys[i:i + 900]
        found = dict(cache.execute(f"SELECT key, val FROM text WHERE key IN ({','.join('?' * len(part))})", part))
        for r, k in zip(keep[i:i + 900], part):
            if k in found:
                r["cached"] = json.loads(found[k])
    cache.close()
    print(f"{sum('cached' in r for r in keep)} of {len(keep)} postings read from the cache", flush=True)

    # The next build's cache: this build's results only, so postings that left the window drop out of it.
    CACHE.with_suffix(".new").unlink(missing_ok=True)
    fresh = sqlite3.connect(CACHE.with_suffix(".new"))
    fresh.execute("CREATE TABLE text (key TEXT PRIMARY KEY, val TEXT)")
    out = []
    for k, (n, computed) in zip(keys, pool.imap(normalize, keep, chunksize=200)):
        val = computed if computed is not None else {f: n[f] for f in TEXT_FIELDS}
        fresh.execute("INSERT OR REPLACE INTO text VALUES (?, ?)", (k, json.dumps(val, ensure_ascii=False)))
        out.append(n)
    fresh.commit()
    fresh.close()
    CACHE.with_suffix(".new").replace(CACHE)
    del keep

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
        "posted_to": posted_to,
        "universe": cfg["universe"],
        "companies": [{k: c.get(k) for k in ("rank", "ticker", "name", "weight_pct", "sector", "career_site",
                                             "adapter", "known_issue", "coverage")} for c in cfg["companies"]],
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

    tpl = (ROOT / "web/template.html").read_text()

    # The website's index.html loads the postings from web/postings/, one gzip file per posted week (the Monday
    # it starts), so no file passes the host's 25 MB limit and unchanged weeks stay cached in the browser.
    weeks = {}
    for row in data["rows"]:
        d = date.fromisoformat(row[fields.index("posted")][:10])
        weeks.setdefault((d - timedelta(days=d.weekday())).isoformat(), []).append(row)
    chunk_dir = ROOT / "web/postings"
    chunk_dir.mkdir(exist_ok=True)
    chunks = []
    for wk in sorted(weeks):
        name = f"postings-{wk}.json.gz"
        blob = gzip.compress(json.dumps(weeks[wk], separators=(",", ":"), ensure_ascii=False).encode(), 9, mtime=0)
        if not (chunk_dir / name).exists() or (chunk_dir / name).read_bytes() != blob:
            (chunk_dir / name).write_bytes(blob)
        chunks.append(name)
    for old_file in chunk_dir.glob("postings-*.json.gz"):
        if old_file.name not in chunks:
            old_file.unlink()
    site = {**data, "rows": [], "chunks": chunks}
    site_json = json.dumps(site, separators=(",", ":"), ensure_ascii=False).encode()
    body = tpl.replace("/*DATA*/null", json.dumps(base64.b64encode(gzip.compress(site_json, 9)).decode()))
    (ROOT / "web/index.html").write_text(
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
        '<meta name="description" content="What America\'s largest employers are hiring for: S&amp;P 500 job postings by '
        'occupation, skills, degree, major, pay and location, updated weekly.">'
        # Impact (Udemy affiliate program) site ownership check
        "<meta name='impact-site-verification' value='beb7fdb3-f4c8-4eae-acb7-033f95d31e4f'>"
        '</head>\n'
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
