"""SQLite store that turns repeated snapshots into a history.

postings:  one row per (company, source_id) with first_seen / last_seen and the latest raw record.
snapshots: one row per (run_date, company) with collected count and the site's reported total.
A posting missing from the latest successful run of its company is treated as closed. A posting seen in a
later run that failed partway (or an earlier run the same day) is still open.
A raw line marked seen_only (listed again, detail page not re-read) only moves last_seen; the stored
record and first_seen stay.
"""
import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS postings (
  company TEXT, source_id TEXT, first_seen TEXT, last_seen TEXT, raw TEXT,
  PRIMARY KEY (company, source_id));
CREATE TABLE IF NOT EXISTS snapshots (
  run_date TEXT, company TEXT, status TEXT, collected INTEGER, site_total INTEGER, detail TEXT,
  PRIMARY KEY (run_date, company));
"""


def connect(root):
    db = sqlite3.connect(Path(root) / "data/lens.db")
    db.executescript(SCHEMA)
    return db


def known_postings(root):
    """Postings already in the history, {company: {source_id: url}}, and each company's collected count in
    its latest successful run. Both are empty when there is no history yet."""
    if not (Path(root) / "data/lens.db").exists():
        return {}, {}
    db = connect(root)
    known = {}
    for company, sid, url in db.execute("SELECT company, source_id, json_extract(raw, '$.url') FROM postings"):
        known.setdefault(company, {})[sid] = url
    last = dict(db.execute("""SELECT company, collected FROM snapshots s WHERE status = 'ok' AND run_date =
                              (SELECT MAX(run_date) FROM snapshots WHERE company = s.company AND status = 'ok')"""))
    db.close()
    return known, last


def ingest_run(root, run_date):
    root = Path(root)
    run_dir = root / "data/raw" / run_date
    log = json.loads((run_dir / "run_log.json").read_text())
    db = connect(root)
    missing = 0
    for t, e in log.items():
        db.execute("INSERT OR REPLACE INTO snapshots VALUES (?,?,?,?,?,?)",
                   (run_date, t, e.get("status"), e.get("collected", 0), e.get("site_total"), e.get("detail")))
        f = run_dir / f"{t}.jsonl"
        if e.get("status") != "ok" or not f.exists():
            continue
        for line in f.open():
            r = json.loads(line)
            if r.get("seen_only"):
                cur = db.execute("UPDATE postings SET last_seen=? WHERE company=? AND source_id=?",
                                 (run_date, t, r["source_id"]))
                missing += cur.rowcount == 0
                continue
            db.execute("""INSERT INTO postings VALUES (?,?,?,?,?)
                          ON CONFLICT(company, source_id) DO UPDATE SET last_seen=excluded.last_seen, raw=excluded.raw""",
                       (t, r["source_id"], run_date, run_date, line))
    db.commit()
    db.close()
    if missing:  # only if the history changed during the run; those postings are re-read next run
        print(f"{missing} seen_only postings were not in the history")


def load_postings(root):
    db = connect(root)
    latest = dict(db.execute("SELECT company, MAX(run_date) FROM snapshots WHERE status='ok' GROUP BY company"))
    rows = []
    for company, sid, first, last, raw in db.execute("SELECT * FROM postings"):
        r = json.loads(raw)
        r.update(first_seen=first, last_seen=last, is_open=(last >= (latest.get(company) or "9999")))
        rows.append(r)
    snaps = [dict(zip(("run_date", "company", "status", "collected", "site_total", "detail"), s))
             for s in db.execute("SELECT * FROM snapshots ORDER BY run_date")]
    db.close()
    return rows, snaps
